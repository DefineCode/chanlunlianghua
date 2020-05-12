# coding: utf-8
import traceback
from copy import deepcopy
import pandas as pd
from functools import lru_cache

from .ta import macd, ma


def is_bei_chi(ka, zs1, zs2, direction="down", mode="bi", adjust=0.9):
	"""判断 zs1 对 zs2 是否有背驰

	:param ka: KlineAnalyze
		缠论的分析结果，即去除包含关系后，识别出分型、笔、线段的K线
	:param direction: str
		default `down`, optional value [`up`, 'down']
	:param zs1: list of datetime
		用于比较的走势，通常是最近的走势
	:param zs2: list of datetime
		被比较的走势，通常是较前的走势
	:param mode: str
		default `bi`, optional value [`zs`, `xd`, `bi`]
		zs  判断两个走势类型之间是否存在背驰
		xd  判断两个线段之间是否存在背驰
		bi  判断两笔之间是否存在背驰
	:param adjust: float
		调整 zs2 的力度，建议设置范围在 0.6 ~ 1.0 之间，默认设置为 0.9；
		其作用是确保 zs1 相比于 zs2 的力度足够小。
	:return:
	"""
	assert zs1[0] > zs2[0], "zs1 必须是最近的走势，用于比较；zs2 必须是较前的走势，被比较。"
	assert zs1[0] < zs1[1], "走势的时间区间定义错误，必须满足 zs[0] < zs[1]"
	assert zs2[0] < zs2[1], "走势的时间区间定义错误，必须满足 zs[0] < zs[1]"

	# df = pd.DataFrame(deepcopy(ka.kline))
	# df = macd(df)
	df = create_df(ka)
	k1 = df[(df['dt'] >= zs1[0]) & (df['dt'] <= zs1[1])]
	k2 = df[(df['dt'] >= zs2[0]) & (df['dt'] <= zs2[1])]

	bc = False
	if mode == 'bi':
		macd_sum1 = sum([abs(x) for x in k1.macd])
		macd_sum2 = sum([abs(x) for x in k2.macd])
		# print("bi: ", macd_sum1, macd_sum2)
		if macd_sum1 < macd_sum2 * adjust:
			bc = True

	elif mode == 'xd' or mode == 'zs':
		if direction == "down":
			macd_sum1 = sum([abs(x) for x in k1.macd if x < 0])
			macd_sum2 = sum([abs(x) for x in k2.macd if x < 0])
		elif direction == "up":
			macd_sum1 = sum([abs(x) for x in k1.macd if x > 0])
			macd_sum2 = sum([abs(x) for x in k2.macd if x > 0])
		else:
			raise ValueError('direction value error')
		# print("xd: ", macd_sum1, macd_sum2)
		if macd_sum1 < macd_sum2 * adjust:
			bc = True

	else:
		raise ValueError("mode value error")

	return bc


def up_zs_number(ka):
	"""检查最新走势的连续向上中枢数量"""
	zs_num = 1
	if len(ka.zs) > 1:
		k_zs = ka.zs[::-1]
		zs_cur = k_zs[0]
		for zs_next in k_zs[1:]:
			if zs_cur['zs'][0] >= zs_next['zs'][1]:
				zs_num += 1
				zs_cur = zs_next
			else:
				break
	return zs_num


def down_zs_number(ka):
	"""检查最新走势的连续向下中枢数量"""
	zs_num = 1
	if len(ka.zs) > 1:
		k_zs = ka.zs[::-1]
		zs_cur = k_zs[0]
		for zs_next in k_zs[1:]:
			if zs_cur['zs'][1] <= zs_next['zs'][0]:
				zs_num += 1
				zs_cur = zs_next
			else:
				break
	return zs_num


def get_ka_feature(ka):
	"""获取 KlineAnalyze 的特征"""
	feature = dict()

	feature["分型标记"] = 1 if ka.fx[-1]['fx_mark'] == 'g' else 0
	feature["笔标记"] = 1 if ka.bi[-1]['fx_mark'] == 'g' else 0
	feature["线段标记"] = 1 if ka.xd[-1]['fx_mark'] == 'g' else 0

	feature['向上笔背驰'] = 1 if ka.bi[-1]['fx_mark'] == 'g' and ka.bi_bei_chi() else 0
	feature['向下笔背驰'] = 1 if ka.bi[-1]['fx_mark'] == 'd' and ka.bi_bei_chi() else 0
	feature['向上线段背驰'] = 1 if ka.xd[-1]['fx_mark'] == 'g' and ka.xd_bei_chi() else 0
	feature['向下线段背驰'] = 1 if ka.xd[-1]['fx_mark'] == 'd' and ka.xd_bei_chi() else 0

	# 均线/MACD相关特征
	ma_params = (5, 20, 120, 250)
	df = create_df(ka, ma_params)
	last = df.iloc[-1].to_dict()
	for p in ma_params:
		feature['收于MA%i上方' % p] = 1 if last['close'] > last['ma%i' % p] else 0

	feature["MACD金叉"] = 1 if last['diff'] > last['dea'] else 0
	feature["MACD死叉"] = 1 if last['diff'] < last['dea'] else 0

	return feature


@lru_cache(maxsize=64)
def is_macd_cross(ka, direction="up"):
	"""判断macd的向上金叉、向下死叉"""
	# df = pd.DataFrame(ka.kline)
	# df = macd(df)
	df = create_df(ka)
	if (direction == "up" and df.iloc[-1]['diff'] > df.iloc[-1]['dea']) \
			or (direction == "down" and df.iloc[-1]['diff'] < df.iloc[-1]['dea']):
		return True
	return False


@lru_cache(maxsize=64)
def create_df(ka, ma_params=(5, 20, 120, 250)):
	df = pd.DataFrame(deepcopy(ka.kline))
	df = macd(df)
	df = ma(df, params=ma_params)
	return df


class KlineAnalyze(object):
	def __init__(self, kline, bi_mode="new", xd_mode="loose", handle_last=True):
		"""

		:param kline: list of dict or pd.DataFrame
			example kline:
			kline = [
				{'symbol': '600797.SH', 'dt': '2020-01-08 11:30:00', 'open': 10.72, 'close': 10.67, 'high': 10.76, 'low': 10.63, 'vol': 4464800.0},
				{'symbol': '600797.SH', 'dt': '2020-01-08 13:30:00', 'open': 10.66, 'close': 10.59, 'high': 10.66, 'low': 10.55, 'vol': 5004800.0},
				{'symbol': '600797.SH', 'dt': '2020-01-08 14:00:00', 'open': 10.58, 'close': 10.41, 'high': 10.6, 'low': 10.38, 'vol': 10650500.0},
				{'symbol': '600797.SH', 'dt': '2020-01-08 14:30:00', 'open': 10.42, 'close': 10.41, 'high': 10.48, 'low': 10.35, 'vol': 6610000.0},
				{'symbol': '600797.SH', 'dt': '2020-01-08 15:00:00', 'open': 10.42, 'close': 10.39, 'high': 10.48, 'low': 10.36, 'vol': 7160500.0}
			]
		:param bi_mode: str
		   笔识别控制参数，默认为 new，表示新笔；如果不想用新笔定义识别，设置为 old
		:param xd_mode: str
			线段识别控制参数，默认为 loose，在这种模式下，只要线段标记内有三笔就满足会识别；另外一个可选值是 strict，
			在 strict 模式下，对于三笔形成的线段，要求其后的一笔不跌破或升破线段最后一笔的起始位置。
		:param handle_last: bool
			是否使用默认的 handle_last 方法，默认值为 True
		"""
		assert bi_mode in ['new', 'old'], "bi_mode 参数错误"
		assert xd_mode in ['loose', 'strict'], "bi_mode 参数错误"
		self.bi_mode = bi_mode
		self.xd_mode = xd_mode
		self.handle_last = handle_last
		self.kline = self._preprocess(kline)
		self.symbol = self.kline[0]['symbol']
		self.latest_price = self.kline[-1]['close']
		self.start_dt = self.kline[0]['dt']
		self.end_dt = self.kline[-1]['dt']
		self.kline_new = self._remove_include()
		self.fx = self._find_fx()
		self.bi = self._find_bi()
		self.xd = self._find_xd()
		self.zs = self._find_zs()
		self.zs_bi = self._find_zs_bi()
		self.__update_kline()

	def __repr__(self):
		return "<chan.analyze.KlineAnalyze of %s, from %s to %s>" % (self.symbol, self.start_dt, self.end_dt)

	@staticmethod
	def _preprocess(kline):
		"""新增分析所需字段"""
		if isinstance(kline, pd.DataFrame):
			kline = [row.to_dict() for _, row in kline.iterrows()]

		results = []
		for k in kline:
			k['fx_mark'], k['fx'], k['bi'], k['xd'] = "o", None, None, None
			results.append(k)
		return results

	def _remove_include(self):
		"""去除包含关系，得到新的K线数据"""
		# 取前两根 K 线放入 k_new，完成初始化
		kline = deepcopy(self.kline)
		k_new = kline[:2]

		for k in kline[2:]:
			# 从 k_new 中取最后两根 K 线计算方向
			k1, k2 = k_new[-2:]
			if k2['high'] > k1['high']:
				direction = "up"
			elif k2['low'] < k1['low']:
				direction = "down"
			else:
				direction = "up"

			# 判断 k2 与 k 之间是否存在包含关系
			cur_h, cur_l = k['high'], k['low']
			last_h, last_l = k2['high'], k2['low']

			# 左包含 or 右包含
			if (cur_h <= last_h and cur_l >= last_l) or (cur_h >= last_h and cur_l <= last_l):
				# 有包含关系，按方向分别处理
				if direction == "up":
					last_h = max(last_h, cur_h)
					last_l = max(last_l, cur_l)
				elif direction == "down":
					last_h = min(last_h, cur_h)
					last_l = min(last_l, cur_l)
				else:
					raise ValueError

				k['high'] = last_h
				k['low'] = last_l
				k_new.pop(-1)
				k_new.append(k)
			else:
				# 无包含关系，更新 K 线
				k_new.append(k)
		return k_new

	def _find_fx(self):
		"""识别线分型标记

		o   非分型
		d   底分型
		g   顶分型

		:return:
		"""
		kn = deepcopy(self.kline_new)
		i = 0
		while i < len(kn):
			if i == 0 or i == len(kn) - 1:
				i += 1
				continue
			k1, k2, k3 = kn[i - 1: i + 2]
			i += 1

			# 顶分型标记
			if k2['high'] > k1['high'] and k2['high'] > k3['high']:
				k2['fx_mark'] = 'g'
				k2['fx'] = k2['high']

			# 底分型标记
			if k2['low'] < k1['low'] and k2['low'] < k3['low']:
				k2['fx_mark'] = 'd'
				k2['fx'] = k2['low']
		self.kline_new = kn

		fx = [{"dt": x['dt'], "fx_mark": x['fx_mark'], "fx": x['fx']} for x in self.kline_new
			  if x['fx_mark'] in ['d', 'g']]
		return fx

	def __extract_potential(self, mode='fx', fx_mark='d'):
		if mode == 'fx':
			points = deepcopy(self.fx)
		elif mode == 'bi':
			points = deepcopy(self.bi)
		else:
			raise ValueError

		seq = [x for x in points if x['fx_mark'] == fx_mark]
		seq = sorted(seq, key=lambda x: x['dt'], reverse=False)

		p = []
		for i in range(len(seq) - 2):
			window = seq[i: i + 3]
			if fx_mark == 'd':
				if window[0][mode] >= window[1][mode] <= window[2][mode]:
					p.append(deepcopy(window[1]))
			elif fx_mark == 'g':
				if window[0][mode] <= window[1][mode] >= window[2][mode]:
					p.append(deepcopy(window[1]))
			else:
				raise ValueError
		return p

	def __handle_hist_bi(self):
		"""识别笔标记：从已经识别出来的分型中确定能够构建笔的分型
		"""
		if self.bi_mode == "new":
			min_k_num = 4
		elif self.bi_mode == "old":
			min_k_num = 5
		else:
			raise ValueError
		self.min_k_num = min_k_num
		kn = self.kline_new

		# 符合标准的分型
		fx_p = []  # 存储潜在笔标记
		fx_p.extend(self.__extract_potential(mode='fx', fx_mark='d'))
		fx_p.extend(self.__extract_potential(mode='fx', fx_mark='g'))

		# 加入满足笔条件的连续两个分型
		fx = self.fx
		for i in range(len(fx) - 1):
			fx1 = fx[i]
			fx2 = fx[i + 1]
			k_num = [x for x in kn if fx1['dt'] <= x['dt'] <= fx2['dt']]
			if len(k_num) >= min_k_num:
				fx_p.append(fx1)
				fx_p.append(fx2)

		fx_p = sorted(fx_p, key=lambda x: x['dt'], reverse=False)

		# 确认哪些分型可以构成笔
		bi = []
		for i in range(len(fx_p)):
			k = deepcopy(fx_p[i])
			k['bi'] = k['fx']
			del k['fx']
			if len(bi) == 0:
				bi.append(k)
			else:
				k0 = bi[-1]
				if k0['fx_mark'] == k['fx_mark']:
					if (k0['fx_mark'] == "g" and k0['bi'] < k['bi']) or \
							(k0['fx_mark'] == "d" and k0['bi'] > k['bi']):
						bi.pop(-1)
						bi.append(k)
				else:
					# 确保相邻两个顶底之间顶大于底
					if (k0['fx_mark'] == 'g' and k['bi'] >= k0['bi']) or \
							(k0['fx_mark'] == 'd' and k['bi'] <= k0['bi']):
						bi.pop(-1)
						continue

					# 一笔的顶底分型之间至少包含5根K线（新笔只需要4根）
					k_num = [x for x in kn if k0['dt'] <= x['dt'] <= k['dt']]
					if len(k_num) >= min_k_num:
						bi.append(k)
		return bi

	def __handle_last_bi(self, bi):
		"""处理最后一个笔标记

		最后一个笔标记后有两种情况：
		1） 出现顶、底分型，使得最后一笔满足定义，加上对应的标记；
		2） 没有出现使得最后一笔满足定义的顶底分型，耐心等待。

		特别的，对应最后一个笔标记：最后一根K线的最高价大于顶，或最后一根K线的最低价大于底，则删除这个标记。
		"""
		last_bi = bi[-1]
		seq = [x for x in self.fx if x['dt'] >= last_bi['dt']]
		sor = sorted(deepcopy(seq), key=lambda x: x['fx'], reverse=False)

		if last_bi['fx_mark'] == 'd' and sor[-1]['fx_mark'] == 'g':
			k = deepcopy(sor[-1])
		elif last_bi['fx_mark'] == 'g' and sor[0]['fx_mark'] == 'd':
			k = deepcopy(sor[0])
		else:
			k = None

		if k:
			k_num = [x for x in self.kline_new if last_bi['dt'] <= x['dt'] <= k['dt']]
			if len(k_num) >= self.min_k_num:
				k['bi'] = k['fx']
				del k['fx']
				bi.append(k)

		# 笔标记后出现新高或新低，则这个笔标记不成立
		last_bi = bi[-1]
		last_k = self.kline_new[-1]
		if (last_bi['fx_mark'] == 'd' and last_k['low'] < last_bi['bi']) \
				or (last_bi['fx_mark'] == 'g' and last_k['high'] > last_bi['bi']):
			bi.pop(-1)
		return bi

	def _find_bi(self):
		bi = self.__handle_hist_bi()
		if self.handle_last:
			bi = self.__handle_last_bi(bi)

		dts = [x["dt"] for x in bi]
		for k in self.kline_new:
			if k['dt'] in dts:
				k['bi'] = k['fx']
		return bi

	def __handle_hist_xd(self):
		"""识别线段标记：从已经识别出来的笔中识别线段"""
		bi_p = []  # 存储潜在线段标记
		bi_p.extend(self.__extract_potential(mode='bi', fx_mark='d'))
		bi_p.extend(self.__extract_potential(mode='bi', fx_mark='g'))
		bi_p = sorted(bi_p, key=lambda x: x['dt'], reverse=False)

		xd = []
		for i in range(len(bi_p)):
			k = deepcopy(bi_p[i])
			k['xd'] = k['bi']
			del k['bi']
			if len(xd) == 0:
				xd.append(k)
			else:
				k0 = xd[-1]
				if k0['fx_mark'] == k['fx_mark']:
					# 处理同一性质的笔标记
					if (k0['fx_mark'] == "g" and k0['xd'] < k['xd']) or \
							(k0['fx_mark'] == "d" and k0['xd'] > k['xd']):
						xd.pop(-1)
						xd.append(k)
				else:
					# 确保相邻两个顶底之间顶大于底
					if (k0['fx_mark'] == 'g' and k['xd'] >= k0['xd']) or \
							(k0['fx_mark'] == 'd' and k['xd'] <= k0['xd']):
						xd.pop(-1)
						continue
					bi_m = [x for x in self.bi if k0['dt'] <= x['dt'] <= k['dt']]

					if len(bi_m) == 2 and len(xd) >= 2:
						k1 = xd[-2]
						if (k1['fx_mark'] == 'g' and k1['xd'] < k['xd']) or \
								(k1['fx_mark'] == 'd' and k1['xd'] > k['xd']):
							xd.pop(-1)
							xd.pop(-1)
							xd.append(k)

					bi_r = [x for x in self.bi if x['dt'] >= k['dt']]
					# 一线段内部至少三笔
					if len(bi_m) >= 4:
						# 两个连续线段标记之间只有三笔的处理，这里区分 loose 和 strict 两种模式
						if len(bi_m) == 4:
							if self.xd_mode == 'loose':
								if (k['fx_mark'] == "g" and bi_m[-1]['bi'] > bi_m[-3]['bi']) \
										or (k['fx_mark'] == "d" and bi_m[-1]['bi'] < bi_m[-3]['bi']):
									xd.append(k)
							elif self.xd_mode == 'strict':
								if len(bi_r) <= 1:
									continue
								lp2 = bi_m[-2]
								rp2 = bi_r[1]
								if (k['fx_mark'] == "g" and lp2['bi'] < rp2['bi'] and bi_m[-1]['bi'] > bi_m[-3]['bi']) \
										or (k['fx_mark'] == "d" and lp2['bi'] > rp2['bi']
											and bi_m[-1]['bi'] < bi_m[-3]['bi']):
									xd.append(k)
							else:
								raise ValueError("xd_mode value error")
						else:
							xd.append(k)
		return xd

	def __handle_last_xd(self, xd):
		"""处理最后一个线段标记

		最后一个线段后有两种情况：
		1） 出现笔的顶、底背驰，对这种情况，在背驰出现的位置加上对应的线段标记；
		2） 没有出现笔的顶、底背驰，不需要进行处理，耐心等待笔的顶、底背驰出现或者小转大出现。

		特别的，对最后一个线段标记：最后一根K线的最高价大于顶，或最后一根K线的最低价大于底，则删除这个标记。

		最后一个线段走势分解

		"""
		last_xd = xd[-1]
		bi_seq = [x for x in self.bi if x['dt'] >= last_xd['dt']]
		bi_sor = sorted(deepcopy(bi_seq), key=lambda x: x['bi'], reverse=False)

		if last_xd['fx_mark'] == 'd':
			bi_m = [x for x in self.bi if bi_sor[-1]['dt'] >= x['dt'] >= last_xd['dt']]
			if len(bi_m) >= 4:
				zs1 = [bi_m[-2]['dt'], bi_m[-1]['dt']]
				zs2 = [bi_m[-4]['dt'], bi_m[-3]['dt']]
				if is_bei_chi(self, zs1, zs2, mode='bi'):
					new = deepcopy(bi_sor[-1])
					new['xd'] = new['bi']
					del new["bi"]
					xd.append(new)

		if last_xd['fx_mark'] == 'g':
			bi_m = [x for x in self.bi if bi_sor[0]['dt'] >= x['dt'] >= last_xd['dt']]
			if len(bi_m) >= 4:
				zs1 = [bi_m[-2]['dt'], bi_m[-1]['dt']]
				zs2 = [bi_m[-4]['dt'], bi_m[-3]['dt']]
				if is_bei_chi(self, zs1, zs2, mode='bi'):
					new = deepcopy(bi_sor[0])
					new['xd'] = new['bi']
					del new["bi"]
					xd.append(new)

		last_k = self.kline_new[-1]
		if (xd[-1]['fx_mark'] == 'd' and last_k['low'] < xd[-1]['xd']) \
				or (xd[-1]['fx_mark'] == 'g' and last_k['high'] > xd[-1]['xd']):
			xd.pop(-1)
		return xd

	def __check_stable_break(self, price, st, end, dir='down', check_num=3):
		"""
		:param price: 价格
		:param st: 起始点 ,dt
		:param end：结束点,dt
		:param check_num: 收盘价连续站稳指定价的数量
		:param dir:方向，'up' 向上突破站稳, '向下突破站稳'
		"""
		tmp_kline = [x for x in self.kline if st <= x['dt'] <= end]
		count = 0
		for i in range(len(tmp_kline)):
			if dir == 'down':
				if tmp_kline[i]['close'] <= price:
					count += 1
				else:
					count = 0
				if count >= check_num and tmp_kline[i]['open'] >= tmp_kline[i]['close']:  # 阴线结束
					return True
			elif dir == 'up':
				if tmp_kline[i]['close'] >= price:
					count += 1
				else:
					count = 0
				if count >= check_num and tmp_kline[i]['open'] <= tmp_kline[i]['close']:  # 阳线结束
					return True
		return False

	def __handle_last_xd_new(self, xd):
		"""处理最后一个线段标记
		1）1+1终结处理当前线段走势
		2）当前笔不创左边临近笔的高点/低点，且随后一笔有效击穿左边临近笔的低点/高点
		3）有效击穿：连续三日收盘价高于/低于对应点，且最后一根线为阳/阴
		4）注意处理隔山打牛包含情况
		最后一个线段走势分解
		"""
		bFind = True
		if len(xd) <= 2:
			return xd
		print("xd = ", xd)
		# first_last_xd = deepcopy(xd[-2])
		xd.pop(-1)
		while bFind:
			last_xd = xd[-1]
			print("last_xd = ", last_xd)
			bFind = False
			bi_seq = [x for x in self.bi if x['dt'] >= last_xd['dt']]
			if len(bi_seq) < 7:  # 至少6笔才能判断
				return xd
			if last_xd['fx_mark'] == 'g':  # 下跌趋势，起始点是高
				dd = deepcopy(bi_seq[1])
				gg = deepcopy(bi_seq[2])
				print(bi_seq)
				for i in range(3, len(bi_seq) - 1, 2):
					if i > 3 and bi_seq[i]['bi'] >= dd['bi']:  # 当出现当前笔没有破前低
						end_bi = self.end_dt if i + 2 >= len(bi_seq) else bi_seq[i + 2]['dt']
						# 再判断是否有效站稳
						if self.__check_stable_break(gg['bi'], bi_seq[i]['dt'], end_bi, dir='up'):
							new = deepcopy(dd)
							new['xd'] = new['bi']
							del new['bi']
							bFind = True
							xd.append(new)
							break
					# 处理包含关系，低低
					dd = deepcopy(bi_seq[i])
					if bi_seq[i + 1]['bi'] < gg['bi']:
						gg = deepcopy(bi_seq[i + 1])
			elif last_xd['fx_mark'] == 'd':  # 上涨趋势，起始点是低
				gg = deepcopy(bi_seq[1])
				dd = deepcopy(bi_seq[2])
				for i in range(3, len(bi_seq) - 1, 2):
					if i > 3 and bi_seq[i]['bi'] <= gg['bi']:  # 当出现当前笔没有破前高
						end_bi = self.end_dt if i + 2 >= len(bi_seq) else bi_seq[i + 2]['dt']
						# 再判断是否有效站稳
						if self.__check_stable_break(dd['bi'], bi_seq[i]['dt'], end_bi, dir='down'):
							new = deepcopy(gg)
							new['xd'] = new['bi']
							del new['bi']
							bFind = True
							xd.append(new)
							break
					# 处理包含关系，高高
					gg = deepcopy(bi_seq[i])
					if bi_seq[i + 1]['bi'] > dd['bi']:
						dd = deepcopy(bi_seq[i + 1])
				# print("dd = ", dd, " gg = ", gg)

		return xd

	def _find_xd(self):
		try:
			xd = self.__handle_hist_xd()
			if self.handle_last:
				# print("handLast = ",xd)
				xd = self.__handle_last_xd_new(xd)

			dts = [x["dt"] for x in xd]
			for k in self.kline_new:
				if k['dt'] in dts:
					k['xd'] = k['fx']
			return xd
		except:
			traceback.print_exc()
			return []

	def _find_zs(self):
		"""查找中枢"""
		if len(self.xd) <= 4:
			return []

		k_xd = self.xd
		k_zs = []
		zs_xd = []

		for i in range(len(k_xd)):
			if len(zs_xd) < 3:
				zs_xd.append(k_xd[i])
				continue
			xd_p = k_xd[i]
			zs_d = max([x['xd'] for x in zs_xd if x['fx_mark'] == 'd'])
			zs_g = min([x['xd'] for x in zs_xd if x['fx_mark'] == 'g'])

			if xd_p['fx_mark'] == "d" and xd_p['xd'] > zs_g:
				# 线段在中枢上方结束，形成三买
				k_zs.append({'zs': (zs_d, zs_g), "zs_xd": deepcopy(zs_xd)})
				zs_xd = deepcopy(k_xd[i - 2:i + 1])
			elif xd_p['fx_mark'] == "g" and xd_p['xd'] < zs_d:
				# 线段在中枢下方结束，形成三卖
				k_zs.append({'zs': (zs_d, zs_g), "zs_xd": deepcopy(zs_xd)})
				zs_xd = deepcopy(k_xd[i - 2:i + 1])
			else:
				zs_xd.append(deepcopy(xd_p))

		if len(zs_xd) >= 4:
			zs_d = max([x['xd'] for x in zs_xd if x['fx_mark'] == 'd'])
			zs_g = min([x['xd'] for x in zs_xd if x['fx_mark'] == 'g'])
			k_zs.append({'zs': (zs_d, zs_g), "zs_xd": deepcopy(zs_xd)})

		return k_zs

	def _find_zs_bi(self):
		if len(self.xd) < 2:
			return []
		k_xd = self.xd
		k_zs = []
		for i in range(0, len(k_xd)):
			xd_st = k_xd[i]
			xd_end = k_xd[i + 1] if i + 1 < len(k_xd) else self.kline[-1]
			bi_m = [x for x in self.bi if xd_st['dt'] <= x['dt'] <= xd_end['dt']]
			if len(bi_m) >= 6:
				zs_bi = []
				xd_zs = []
				j = 1
				while j < len(bi_m) - 1:
					if len(zs_bi) < 4:  # 少于三笔
						zs_bi.append(bi_m[j])
						zs_bi.append(bi_m[j + 1])
						j += 2
						continue
					zs_d = max([x['bi'] for x in zs_bi[:4] if x['fx_mark'] == 'd'])
					zs_g = min([x['bi'] for x in zs_bi[:4] if x['fx_mark'] == 'g'])
					if zs_g <= zs_d:
						zs_bi.pop(0)
						zs_bi.pop(0)
						continue
					if bi_m[j + 1]['fx_mark'] == 'g' and bi_m[j + 1]['bi'] < zs_d:
						xd_zs.append({'zs': (zs_d, zs_g), "zs_qujian": (zs_bi[0], zs_bi[-1])})
						zs_bi = []
					elif bi_m[j + 1]['fx_mark'] == 'd' and bi_m[j + 1]['bi'] > zs_g:
						xd_zs.append({'zs': (zs_d, zs_g), "zs_qujian": (zs_bi[0], zs_bi[-1])})
						zs_bi = []
					else:
						zs_bi.append(bi_m[j])
						zs_bi.append(bi_m[j + 1])
						j += 2
				if len(zs_bi) >= 4:
					zs_d = max([x['bi'] for x in zs_bi[:4] if x['fx_mark'] == 'd'])
					zs_g = min([x['bi'] for x in zs_bi[:4] if x['fx_mark'] == 'g'])
					if zs_d < zs_g:
						xd_zs.append({'zs': (zs_d, zs_g), "zs_qujian": (zs_bi[0], zs_bi[-1])})
				if len(xd_zs) > 0:
					zoushi = []
					zoushi.append((xd_st['dt'], xd_zs[0]['zs_qujian'][0]['dt']))
					for i in range(1, len(xd_zs)):
						zoushi.append((xd_zs[i - 1]['zs_qujian'][1]['dt'], xd_zs[i]['zs_qujian'][0]['dt']))
					zoushi.append((xd_zs[-1]['zs_qujian'][1]['dt'], xd_end['dt']))
					tmp = {'xd_qujian': (xd_st, xd_end), 'total_zs': deepcopy(xd_zs), 'zoushi': deepcopy(zoushi)}
					k_zs.append(tmp)
		return k_zs

	def __update_kline(self):
		kn_map = {x['dt']: x for x in self.kline_new}
		for k in self.kline:
			k1 = kn_map.get(k['dt'], None)
			if k1:
				k['fx_mark'], k['fx'], k['bi'], k['xd'] = k1['fx_mark'], k1['fx'], k1['bi'], k1['xd']

	def zs_mean(self, n=6, mode='xd'):
		"""计算最近 n 个走势的平均波动幅度

		:param n: int
			线段数量
		:param mode: str
			xd -> 线段平均波动； bi -> 笔平均波动
		:return: float
		"""
		if mode == 'xd':
			latest_zs = deepcopy(self.xd[-n - 1:])
			for x in latest_zs:
				x['fx'] = x['xd']
		elif mode == 'bi':
			latest_zs = deepcopy(self.bi[-n - 1:])
			for x in latest_zs:
				x['fx'] = x['bi']
		else:
			raise ValueError("mode value error, only support 'xd' or 'bi'")

		wave = []
		for i in range(len(latest_zs) - 1):
			x1 = latest_zs[i]['fx']
			x2 = latest_zs[i + 1]['fx']
			w = abs(x1 - x2) / x1
			wave.append(w)
		return round(sum(wave) / len(wave), 2)

	def bi_bei_chi(self):
		"""判断最后一笔是否背驰"""
		bi = deepcopy(self.bi)
		# 最后一笔背驰出现的两种情况：
		# 1）向上笔新高且和前一个向上笔不存在包含关系；
		# 2）向下笔新低且和前一个向下笔不存在包含关系。
		if (bi[-1]['fx_mark'] == 'g' and bi[-1]["bi"] > bi[-3]["bi"] and bi[-2]["bi"] > bi[-4]["bi"]) or \
				(bi[-1]['fx_mark'] == 'd' and bi[-1]['bi'] < bi[-3]['bi'] and bi[-2]['bi'] < bi[-4]['bi']):
			zs1 = [bi[-2]['dt'], bi[-1]['dt']]
			zs2 = [bi[-4]['dt'], bi[-3]['dt']]
			return is_bei_chi(self, zs1, zs2, mode="bi")
		else:
			return False

	def xd_bei_chi(self):
		"""判断最后一个线段是否背驰"""
		xd = deepcopy(self.xd)
		last_xd = xd[-1]
		if last_xd['fx_mark'] == 'g':
			direction = "up"
		elif last_xd['fx_mark'] == 'd':
			direction = "down"
		else:
			raise ValueError

		# 最后一个线段背驰出现的两种情况：
		# 1）向上线段新高且和前一个向上线段不存在包含关系；
		# 2）向下线段新低且和前一个向下线段不存在包含关系。
		if (last_xd['fx_mark'] == 'g' and xd[-1]["xd"] > xd[-3]["xd"] and xd[-2]["xd"] > xd[-4]["xd"]) or \
				(last_xd['fx_mark'] == 'd' and xd[-1]['xd'] < xd[-3]['xd'] and xd[-2]['xd'] < xd[-4]['xd']):
			zs1 = [xd[-2]['dt'], xd[-1]['dt']]
			zs2 = [xd[-4]['dt'], xd[-3]['dt']]
			return is_bei_chi(self, zs1, zs2, direction=direction, mode="xd")
		else:
			return False

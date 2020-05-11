	def __check_stable_break(self, price, st, end, dir='down', check_num=3):
		"""
		:param price: 价格
		:param st: 起始点
		:param end：结束点
		:param check_num: 收盘价连续站稳指定价的数量
		:param dir:方向，'up' 向上突破站稳, '向下突破站稳'
		"""
		tmp_kline = [x for x in self.kline if st['dt'] <= x['dt'] <= end['dt']]
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
		1）取出最后一段，计算出dt >= 此段起始点的笔
		2）每个逆向笔记录成一个K，从左至右记录GD，（下跌低低，上涨高高）
		3）若出现逆向笔，相对记录的GD 形成不包含分型时,再进行连续三日站稳判断处理

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
					# 处理包含关系，低低
					if bi_seq[i]['bi'] < dd['bi']:
						dd = deepcopy(bi_seq[i])
					if bi_seq[i + 1]['bi'] < gg['bi']:
						gg = deepcopy(bi_seq[i + 1])
					if i > 3 and bi_seq[i]['bi'] >= dd['bi']:  # 当出现当前笔没有破前低
						end_bi = bi_seq[i + 1] if i + 2 >= len(bi_seq) else bi_seq[i + 2]
						# 再判断是否有效站稳
						if self.__check_stable_break(gg['bi'], bi_seq[i], end_bi, dir='up'):
							new = deepcopy(dd)
							new['xd'] = new['bi']
							del new['bi']
							bFind = True
							xd.append(new)
			elif last_xd['fx_mark'] == 'd':  # 上涨趋势，起始点是低
				gg = deepcopy(bi_seq[1])
				dd = deepcopy(bi_seq[2])
				for i in range(3, len(bi_seq) - 1, 2):
					# 处理包含关系，高高
					if bi_seq[i]['bi'] > gg['bi']:
						gg = deepcopy(bi_seq[i])
					if bi_seq[i + 1]['bi'] > dd['bi']:
						dd = deepcopy(bi_seq[i + 1])
					# print("dd = ", dd, " gg = ", gg)
					if i > 3 and bi_seq[i]['bi'] <= gg['bi']:  # 当出现当前笔没有破前高
						end_bi = bi_seq[i + 1] if i + 2 >= len(bi_seq) else bi_seq[i + 2]
						# 再判断是否有效站稳
						if self.__check_stable_break(dd['bi'], bi_seq[i], end_bi, dir='down'):
							new = deepcopy(gg)
							new['xd'] = new['bi']
							del new['bi']
							bFind = True
							xd.append(new)
		return xd

	def __check_stable_break(self, price, dt, check_num=3, dir = 'down'):
		"""
		:param price: 需要站稳的价格
		:param dt: 当时的时间
		:param check_num: 收盘价连续站稳指定价的数量
		:param dir:方向，'up' 向上突破站稳, '向下突破站稳'
		"""
		tmp_kline = [x for x in self.kline if x['dt'] >= dt]
		

	def __handle_last_xd_new(self, xd):
		"""处理最后一个线段标记
		1）取出最后一段，计算出dt >= 此段起始点的笔
		2）每个逆向笔记录成一个K，从左至右记录GD，（下跌低低，上涨高高）
		3）若出现逆向笔，相对记录的GD 形成不包含分型时,再进行连续三日站稳判断处理

		最后一个线段走势分解

		"""
		last_xd = xd[-1]
		xd.pop(-1)
		bi_seq = [x for x in self.bi if x['dt'] >= last_xd['dt']]
		if last_xd['fx_mark'] == 'g':
			if len(bi_seq) >= 7: # 至少6笔才能判断
				dd = deepcopy(bi_seq[1])
				gg = deepcopy(bi_seq[2])
				for i in range(3, len(bi_seq) - 3, 2) :
					#处理包含关系
					if dd['bi'] > bi_seq[i]['bi']:
						dd = deepcopy(bi_seq[i])
					if gg['bi'] > bi_seq[i+1]['bi']:
						gg = deepcopy(bi_seq[i+1])
					# 出现低分型
					if dd['bi'] <= bi_seq[i+2]['bi'] and gg['bi'] <= bi_seq[i+3]['bi']:
						#再判断是否有效站稳

						new = deepcopy(dd)
						new['xd'] = new['bi']
						del new['bi']
						xd.append(new)

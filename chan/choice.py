# coding: utf-8
"""
此文件实现择股相关函数
"""


from .analyze import KlineAnalyze
from copy import deepcopy


def is_lei_second_buy(ka, small_ka=None, big_ka=None, pf=False):
	"""
		1.当前线段是上升段，且存在中枢
		2.中枢的振幅合理，中枢结构比较规整（需要想确定的规则）
		3.高级别20均线回抽

	:param ka: 本级别， KlineAnalyze
	:param small_ka: 次级别， KlineAnalyze
	:param big_ka: 高级别， KlineAnalyze
	:param pf: "高精度优先模式"
	:return:
	"""
	# 本级别最后一个完成的走势是低，当前是一个上涨趋势
	if len(ka.xd) >= 2 and ka.xd[-1]['fx_mark'] == 'd':
		xd_st = deepcopy(ka.zs_bi[-1]['xd_qujian'][0])
		xd_end = deepcopy(ka.zs_bi[-1]['xd_qujian'][1])
		#zs_bi {'xd_qujian': (xd_st, xd_end), 'total_zs': deepcopy(xd_zs), 'zoushi': deepcopy(zoushi)}
		#存在一个中枢
		if xd_st['dt'] >= ka.xd[-1]['dt'] and len(ka.zs_bi[-1]['total_zs']) == 1:
			cur_zs = ka.zs_bi[-1]['total_zs'][0]
			if cur_zs['zs_qujian'][1]['fx_mark'] == 'd' and cur_zs['zs_qujian'][1]['dt'] >= ka.bi[-1]['dt']:
				return True
	return False
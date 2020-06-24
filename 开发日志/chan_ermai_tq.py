# coding: utf-8
import os
from tqsdk import TqApi, TqBacktest, TqSim
from datetime import date, datetime, timedelta
from copy import deepcopy
from pathlib import Path
import traceback
from czsc import KlineAnalyze
from czsc.analyze import create_df
from czsc.solid import is_second_buy, is_second_sell
from zb.utils import create_logger

# 环境准备： pip install tqsdk zb czsc


class TradeAnalyze:
    """5分钟第二类买卖点"""
    def __init__(self, klines):
        self.klines = klines
        self.ka_1min = KlineAnalyze(self.klines['1分钟'], name='1分钟')
        self.ka_5min = KlineAnalyze(self.klines['5分钟'], name="5分钟")
        self.ka_30min = KlineAnalyze(self.klines['30分钟'], name="30分钟")
        #self.ka_D = KlineAnalyze(self.klines['日线'], name='日线')
        self.symbol = self.ka_1min.symbol
        self.end_dt = self.ka_1min.end_dt
        self.latest_price = self.ka_1min.latest_price
        self.s = self.signals()
        self.desc = self.__doc__

    def signals(self):
        """计算交易决策需要的状态信息"""
        s = {"symbol": self.symbol,
             "dt": self.end_dt,
             "base_price": self.ka_5min.xd[-1]['xd'],
             "latest_price": self.latest_price,
             "5分钟二买": False,
             "5分钟二买止损价":0,
             "5分钟二卖": False,
             "5分钟二卖止损价": 0,
             }

        ka = self.ka_5min
        ka1 = self.ka_30min
        ka2 = self.ka_1min
        tmp_buy = is_second_buy(ka,ka1, ka2, pf=False)
        if tmp_buy["操作提示"] == "二买":
            s['5分钟二买'] = True
            s['5分钟二买止损价'] = tmp_buy["基准价格"]
        tmp_sell = is_second_sell(ka,ka1, ka2, pf=False)
        if tmp_sell["操作提示"] == "二卖":
            s['5分钟二卖'] = True
            s['5分钟二卖止损价'] = tmp_sell["基准价格"]

        return {k: v for k, v in s.items()}


class TradeInfo:
    def __init__(self, zhisun = 0.01):
        self.zhisun_percent = zhisun  # 根据最大止损百分比开仓位
        self.zhisun_price = 0  # 当前止损价格
        self.kaicang_price = 0
        self.pos_short = 0  # 当前空单仓位
        self.pos_long = 0  # 当前多单仓位

def format_kline(kline):
    """格式化K线"""
    def __convert_time(t):
        try:
            dt = datetime.utcfromtimestamp(t/1000000000)
            dt = dt + timedelta(hours=8)    # 中国默认时区
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return ""

    kline['dt'] = kline['datetime'].apply(__convert_time)
    kline['vol'] = kline['volume']
    columns = ['symbol', 'dt', 'open', 'close', 'high', 'low', 'vol']
    df = kline[columns]
    df = df.dropna(axis=0)
    df.sort_values('dt', inplace=True, ascending=True)
    df.reset_index(drop=True, inplace=True)
    return df


if __name__ == '__main__':
    start_dt = date(2020, 6, 15)
    end_dt = date(2020, 6, 23)
    init_balance = 100000
    #port = '53318'
    freqs_k_count = {"1分钟": 1000, "5分钟": 1000, "30分钟": 300}

    max_positions = {
        "KQ.i@SHFE.rb": 10,
    }
    pinzhong_trade = {
        "KQ.i@SHFE.rb": TradeInfo(),
    }
    data_path = f"./logs/S05_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    Path(data_path).mkdir(parents=True, exist_ok=False)
    file_log = os.path.join(data_path, "backtest.log")
    file_signals = os.path.join(data_path, "signals.txt")

    logger = create_logger(log_file=file_log, cmd=True, name="S")
    logger.info(f"标的配置：{max_positions}")
    #logger.info(f"前端地址：http://127.0.0.1:{port}")
    logger.info(f"策略描述：{TradeAnalyze.__doc__}")

    account = TqSim(init_balance=init_balance)
    backtest = TqBacktest(start_dt=start_dt, end_dt=end_dt)
    api = TqApi(account=account, backtest=backtest)
    symbols = list(max_positions.keys())
    freqs = list(freqs_k_count.keys())

    freq_seconds = {"1分钟": 60, "5分钟": 60 * 5, "15分钟": 60 * 15,
                    "30分钟": 60 * 30, "60分钟": 60 * 60, "日线": 3600 * 24}

    # 订阅K线
    symbols_klines = {s: dict() for s in symbols}
    for symbol in symbols:
        for freq in freqs:
            symbols_klines[symbol][freq] = api.get_kline_serial(symbol,
                                                                freq_seconds[freq],
                                                                data_length=freqs_k_count[freq])

    account = api.get_account()
    positions = api.get_position()

    while True:
        api.wait_update()
        for symbol in symbols:
            if api.is_changing(symbols_klines[symbol]["5分钟"]):
                klines = {k: format_kline(deepcopy(symbols_klines[symbol][k])) for k in freqs}
                try:
                    ta = TradeAnalyze(klines)
                    with open(file_signals, 'a', encoding='utf-8') as f:
                        f.write(str(ta.s) + "\n")
                except:
                    traceback.print_exc()
                    continue
                cur_pos = positions.get(symbol, None)
                if cur_pos:
                    pinzhong_trade[symbol].pos_long = cur_pos.pos_long
                    pinzhong_trade[symbol].pos_short = cur_pos.pos_short

                if ta.s['5分钟二买'] and pinzhong_trade[symbol].pos_long == 0:
                    pinzhong_trade[symbol].zhisun_price = ta.s['5分钟二买止损价']
                    offset = abs(ta.latest_price - pinzhong_trade[symbol].zhisun_price) * 10
                    if offset == 0:
                        pinzhong_trade[symbol].pos_long = 5
                    else:
                        pinzhong_trade[symbol].pos_long = min(int(account.balance * pinzhong_trade[symbol].zhisun_percent / offset), 10)
                    pinzhong_trade[symbol].kaicang_price = ta.latest_price
                    order = api.insert_order(symbol=symbol, direction="BUY", offset="OPEN",
                                             volume=pinzhong_trade[symbol].pos_long)
                    logger.info(f"{symbol} - 二买：{ta.end_dt, pinzhong_trade[symbol].pos_long}")
                if ta.s['5分钟二卖'] and pinzhong_trade[symbol].pos_short == 0:
                    pinzhong_trade[symbol].zhisun_price = ta.s['5分钟二卖止损价']
                    offset = abs(ta.latest_price - pinzhong_trade[symbol].zhisun_price) * 10
                    if offset == 0:
                        pinzhong_trade[symbol].pos_short = 5
                    else:
                        pinzhong_trade[symbol].pos_short = min(int(account.balance * pinzhong_trade[symbol].zhisun_percent / offset), 10)
                    pinzhong_trade[symbol].kaicang_price = ta.latest_price
                    order = api.insert_order(symbol=symbol, direction="SELL", offset="OPEN",
                                             volume=pinzhong_trade[symbol].pos_short)

                    logger.info(f"{symbol} - 二卖：{ta.end_dt, pinzhong_trade[symbol].pos_short}")


            if api.is_changing(symbols_klines[symbol]["1分钟"]):
                price = symbols_klines[symbol]["1分钟"].close.iloc[-1]
                offset = max(abs(pinzhong_trade[symbol].kaicang_price - pinzhong_trade[symbol].zhisun_price), 1)
                curoffset = price - pinzhong_trade[symbol].zhisun_price
                # 多单止损
                if pinzhong_trade[symbol].pos_long > 0 and curoffset <= 0:
                    order = api.insert_order(symbol=symbol, direction="SELL", offset="CLOSE",
                                             volume=pinzhong_trade[symbol].pos_long)

                if pinzhong_trade[symbol].pos_long > 0 and offset * 2 <= abs(curoffset):
                    order = api.insert_order(symbol=symbol, direction="SELL", offset="CLOSE",
                                             volume=pinzhong_trade[symbol].pos_long)

                # 空单止损
                if pinzhong_trade[symbol].pos_short > 0 and curoffset >= 0:
                    order = api.insert_order(symbol=symbol, direction="BUY", offset="CLOSE",
                                             volume=pinzhong_trade[symbol].pos_long)

                if pinzhong_trade[symbol].pos_short > 0 and offset * 2 <= abs(curoffset):
                    order = api.insert_order(symbol=symbol, direction="BUY", offset="CLOSE",
                                             volume=pinzhong_trade[symbol].pos_long)
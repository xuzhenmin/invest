from futu import OpenQuoteContext, RET_OK, SubType
from typing import Dict, Any, List

class FutuClient:
    def __init__(self, host='127.0.0.1', port=11111):
        self.ctx = OpenQuoteContext(host=host, port=port)
        print(f"FutuClient initialized, connecting to {host}:{port}")
        self.subscribed_symbols = set()
        
        initial_symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "HK.00700", "US.AAPL"]
        self._subscribe_symbols(initial_symbols, [SubType.QUOTE])

    def _subscribe_symbols(self, symbols: List[str], sub_types: List[SubType]):
        """Helper to subscribe to a list of symbols for specified sub_types."""
        to_subscribe = [s for s in symbols if s not in self.subscribed_symbols]
        if to_subscribe:
            ret, data = self.ctx.subscribe(to_subscribe, sub_types)
            if ret == RET_OK:
                print(f"Successfully subscribed to {to_subscribe} for types {sub_types}")
                self.subscribed_symbols.update(to_subscribe)
            else:
                print(f"Failed to subscribe to {to_subscribe} for types {sub_types}: {data}")

    def get_realtime_quote(self, symbol: str) -> Dict[str, Any]:
        """
        获取实时行情数据
        Ensure the symbol is subscribed before fetching real-time quote.
        """
        if symbol not in self.subscribed_symbols:
            print(f"Symbol {symbol} not subscribed. Attempting to subscribe...")
            self._subscribe_symbols([symbol], [SubType.QUOTE])
            if symbol not in self.subscribed_symbols:
                raise Exception(f"未能订阅 {symbol} 的行情，无法获取实时数据")

        raw_result = self.ctx.get_stock_quote([symbol])
        if not isinstance(raw_result, tuple) or len(raw_result) < 2:
            raise Exception(f"Futu API for real-time quote returned unexpected format: {raw_result}")
        ret, data = raw_result[0], raw_result[1]

        if ret == RET_OK:
            if not data.empty:
                return data.to_dict('records')[0]
            else:
                raise Exception(f"未能获取 {symbol} 的实时行情数据，可能是代码错误或无数据")
        else:
            raise Exception(f"Futu实时行情获取失败: {data}")

    def get_kline(self, symbol: str, ktype: str = 'K_DAY', num: int = 100) -> List[Dict[str, Any]]:
        """
        获取历史K线数据
        Historical K-line typically does not require a prior subscription.
        """
        raw_result = self.ctx.request_history_kline(symbol, ktype=ktype, max_count=num)
        if not isinstance(raw_result, tuple) or len(raw_result) < 2:
            raise Exception(f"Futu API for K-line returned unexpected format: {raw_result}")
        ret, data = raw_result[0], raw_result[1]

        if ret == RET_OK:
            if not data.empty:
                return data.to_dict('records')
            else:
                raise Exception(f"未能获取 {symbol} 的 {ktype} K线数据，可能是代码错误或无数据")
        else:
            raise Exception(f"Futu历史K线获取失败: {data}")

    def close(self):
        self.ctx.close()
        print("FutuClient connection closed.") 

"""
交易日历工具
提供交易日判断、节假日检测等功能
"""

import datetime
from typing import Optional
import logging

try:
    from futu import OpenQuoteContext, RET_OK, TradeDateMarket
    FUTU_AVAILABLE = True
except ImportError:
    FUTU_AVAILABLE = False

logger = logging.getLogger(__name__)

class TradingCalendar:
    """交易日历工具类"""
    
    # 周末映射
    WEEKEND_DAYS = {5, 6}  # 周六(5)、周日(6)
    
    # 市场代码映射
    MARKET_MAP = {
        'SH': TradeDateMarket.CN,
        'SZ': TradeDateMarket.CN,
        'HK': TradeDateMarket.HK,
        'US': TradeDateMarket.US,
        'CN': TradeDateMarket.CN,
    }
    
    @staticmethod
    def is_weekday(date: datetime.date) -> bool:
        """
        判断是否为工作日（周一到周五）
        :param date: 日期
        :return: True如果是工作日
        """
        return date.weekday() not in TradingCalendar.WEEKEND_DAYS
    
    @staticmethod
    def is_trading_day(date: datetime.date, market: str = 'CN') -> bool:
        """
        判断是否为交易日（考虑节假日）
        :param date: 日期
        :param market: 市场代码
        :return: True如果是交易日
        """
        if not FUTU_AVAILABLE:
            # 如果Futu不可用，只判断工作日
            return TradingCalendar.is_weekday(date)
        
        try:
            # 使用Futu API获取交易日历
            quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
            
            market_code = TradingCalendar.MARKET_MAP.get(market.upper())
            if not market_code:
                # 未知市场，按工作日处理
                return TradingCalendar.is_weekday(date)
            
            # 查询该日是否为交易日
            ret, data = quote_ctx.request_trading_days(
                market=market_code,
                start=date.strftime('%Y-%m-%d'),
                end=date.strftime('%Y-%m-%d')
            )
            
            quote_ctx.close()
            
            if ret == RET_OK and data:
                # 检查返回的交易日数据
                for item in data:
                    if item.get('time') == date.strftime('%Y-%m-%d'):
                        trade_type = item.get('trade_date_type', '')
                        # WHOLE表示全天交易，MORNING表示上午交易，AFTERNOON表示下午交易
                        return trade_type in ['WHOLE', 'MORNING', 'AFTERNOON']
            
            # 默认按工作日处理
            return TradingCalendar.is_weekday(date)
            
        except Exception as e:
            logger.warning(f"获取交易日历失败: {e}，使用工作日判断")
            return TradingCalendar.is_weekday(date)
    
    @staticmethod
    def get_next_trading_day(date: datetime.date, market: str = 'CN') -> datetime.date:
        """
        获取下一个交易日
        :param date: 起始日期
        :param market: 市场代码
        :return: 下一个交易日
        """
        next_day = date + datetime.timedelta(days=1)
        while not TradingCalendar.is_trading_day(next_day, market):
            next_day += datetime.timedelta(days=1)
        return next_day
    
    @staticmethod
    def get_previous_trading_day(date: datetime.date, market: str = 'CN') -> datetime.date:
        """
        获取上一个交易日
        :param date: 起始日期
        :param market: 市场代码
        :return: 上一个交易日
        """
        prev_day = date - datetime.timedelta(days=1)
        while not TradingCalendar.is_trading_day(prev_day, market):
            prev_day -= datetime.timedelta(days=1)
        return prev_day
    
    @staticmethod
    def get_trading_days_between(start_date: datetime.date, 
                               end_date: datetime.date, 
                               market: str = 'CN') -> list:
        """
        获取两个日期之间的所有交易日
        :param start_date: 开始日期
        :param end_date: 结束日期
        :param market: 市场代码
        :return: 交易日列表
        """
        trading_days = []
        current_date = start_date
        
        while current_date <= end_date:
            if TradingCalendar.is_trading_day(current_date, market):
                trading_days.append(current_date)
            current_date += datetime.timedelta(days=1)
        
        return trading_days

# 便捷函数
def is_today_trading_day(market: str = 'CN') -> bool:
    """判断今天是否为交易日"""
    return TradingCalendar.is_trading_day(datetime.date.today(), market)

def get_today_market_status(market: str = 'CN') -> dict:
    """获取今日市场状态"""
    today = datetime.date.today()
    return {
        'date': today.strftime('%Y-%m-%d'),
        'weekday': today.strftime('%A'),
        'is_trading_day': TradingCalendar.is_trading_day(today, market),
        'is_weekday': TradingCalendar.is_weekday(today)
    }

if __name__ == "__main__":
    # 测试交易日判断
    today = datetime.date.today()
    print(f"今天是: {today.strftime('%Y-%m-%d %A')}")
    print(f"是否为工作日: {TradingCalendar.is_weekday(today)}")
    print(f"是否为交易日: {is_today_trading_day('CN')}")
    print(f"下一个交易日: {TradingCalendar.get_next_trading_day(today)}")
    print(f"上一个交易日: {TradingCalendar.get_previous_trading_day(today)}")

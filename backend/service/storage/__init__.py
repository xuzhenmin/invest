"""
数据库服务模块
提供SQLite数据库的完整功能支持

使用示例:
    from backend.service import data_service, query_service
    from backend.service.models import StockInfo, TradeRecord
    
    # 保存股票信息
    stock = StockInfo(code="00700", name="腾讯控股", market="HK")
    data_service.save_stock_info(stock)
    
    # 查询股票信息
    stock_info = query_service.get_stock_info("00700")
    
    # 获取所有持仓
    positions = query_service.get_positions()
"""

from .database_manager import db_manager
from .data_service import data_service
from .query_service import query_service
from .models import (
    StockInfo, TradeRecord, Position, StrategySignal, 
    MarketData, TradeFailure, DiagnosisReport,
    OrderStatus, TradeDirection, RiskLevel, Recommendation
)

__all__ = [
    'db_manager',
    'data_service', 
    'query_service',
    'StockInfo',
    'TradeRecord',
    'Position',
    'StrategySignal',
    'MarketData',
    'TradeFailure',
    'DiagnosisReport',
    'OrderStatus',
    'TradeDirection',
    'RiskLevel',
    'Recommendation'
]

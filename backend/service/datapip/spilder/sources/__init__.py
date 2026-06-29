"""
具体宏观数据源实现集合

提供 ``build_default_sources()`` 工厂方法，按优先级返回数据源列表。
"""

from typing import List

from ..base import MacroDataSource
from .akshare_source import AkshareSource
from .financial_api_source import FinancialApiSource
from .sina_source import SinaSource
from .yfinance_source import YFinanceSource

__all__ = [
    'AkshareSource',
    'FinancialApiSource',
    'YFinanceSource',
    'SinaSource',
    'build_default_sources',
]


def build_default_sources() -> List[MacroDataSource]:
    """
    构建默认数据源列表（按优先级升序）。

    顺序：financial_api → akshare → sina → yfinance
    （financial_api 对 CPI/PMI/PPI 等国内宏观最可靠且优先级最高，
     akshare 覆盖全部 symbol 作为兜底，sina 接汇率类备份，yfinance 兜底美股美债）
    """
    return [
        FinancialApiSource(),
        AkshareSource(),
        SinaSource(),
        YFinanceSource(),
    ]

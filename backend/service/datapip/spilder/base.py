"""
宏观数据源抽象基类与异常定义

约定标准返回结构：
    DataFrame 必须包含三列
      - date         : str, 'YYYY-MM-DD'，数据期日（统计期）
      - value        : float，数值
      - publish_date : str, 'YYYY-MM-DD'，公布日（日频数据 = date；月频数据为实际公布日）
"""

from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd


REQUIRED_COLUMNS = ('date', 'value', 'publish_date')


class MacroDataError(Exception):
    """宏观数据获取相关异常"""

    def __init__(self, message: str, symbol: Optional[str] = None,
                 source: Optional[str] = None):
        super().__init__(message)
        self.symbol = symbol
        self.source = source


class MacroDataSource(ABC):
    """
    宏观数据源抽象基类

    每个具体源（akshare / yfinance / sina / treasury 等）需要实现：
      - ``supports(symbol)``：是否能提供该宏观资产的数据
      - ``fetch(symbol, start, end)``：拉取数据并返回标准结构 DataFrame
    """

    name: str = 'unknown'
    priority: int = 100   # 数字越小优先级越高

    @abstractmethod
    def supports(self, symbol: str) -> bool:
        """该数据源是否支持指定 macro symbol。"""

    @abstractmethod
    def fetch(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        拉取 [start_date, end_date] 区间的数据。

        Returns:
            DataFrame[date, value, publish_date]，按 date 升序。
            未取到数据时返回空 DataFrame（保留列结构）。

        Raises:
            MacroDataError: 数据源异常或结构不合法。
        """

    # ------------------------------------------------------------------
    # 工具方法（子类公共）
    # ------------------------------------------------------------------

    @staticmethod
    def empty_df() -> pd.DataFrame:
        """返回符合标准结构的空 DataFrame。"""
        return pd.DataFrame(columns=list(REQUIRED_COLUMNS))

    @staticmethod
    def normalize_df(df: pd.DataFrame, date_col: str, value_col: str,
                     publish_date_col: Optional[str] = None) -> pd.DataFrame:
        """
        把异构源的 DataFrame 转成标准结构。

        Args:
            df: 原始数据
            date_col: 数据期日列名
            value_col: 数值列名
            publish_date_col: 公布日列名（None 表示 = date）
        """
        if df is None or df.empty:
            return MacroDataSource.empty_df()

        out = pd.DataFrame()
        out['date'] = pd.to_datetime(df[date_col], errors='coerce').dt.strftime('%Y-%m-%d')
        out['value'] = pd.to_numeric(df[value_col], errors='coerce')
        if publish_date_col and publish_date_col in df.columns:
            out['publish_date'] = pd.to_datetime(
                df[publish_date_col], errors='coerce'
            ).dt.strftime('%Y-%m-%d')
        else:
            out['publish_date'] = out['date']

        out = out.dropna(subset=['date', 'value']).copy()
        out = out.sort_values('date').reset_index(drop=True)
        return out

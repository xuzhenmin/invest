"""
宏观数据多源调度器

按优先级遍历各 ``MacroDataSource``，遇到失败自动降级到下一个数据源。
对外只暴露一个 ``fetch(symbol, start, end)`` 入口。
"""

from typing import List, Optional

import pandas as pd

from utils.logger_config import get_logger

from .base import MacroDataError, MacroDataSource
from .quality_rules import filter_dataframe
from .sources import build_default_sources

logger = get_logger(__name__)


class MacroDataFetcher:
    """多源宏观数据获取器（带降级 + 质量过滤）"""

    def __init__(self, sources: Optional[List[MacroDataSource]] = None):
        self.sources: List[MacroDataSource] = sources or build_default_sources()
        # 按优先级升序排序（数字越小越优先）
        self.sources.sort(key=lambda s: getattr(s, 'priority', 100))

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    def fetch(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        拉取 [start_date, end_date] 区间数据，按优先级降级。

        Returns:
            标准结构 DataFrame[date, value, publish_date]，按 date 升序。
            所有源都失败时返回空 DataFrame（不抛异常，让上游决定如何处理）。
        """
        last_error: Optional[Exception] = None
        for src in self.sources:
            try:
                if not src.supports(symbol):
                    continue
                df = src.fetch(symbol, start_date, end_date)
            except MacroDataError as e:
                logger.warning(f"[fetcher] source={src.name} symbol={symbol} 失败: {e}")
                last_error = e
                continue
            except Exception as e:  # 防御性兜底
                logger.warning(
                    f"[fetcher] source={src.name} symbol={symbol} 未预期异常: {e}"
                )
                last_error = e
                continue

            if df is None or df.empty:
                logger.info(
                    f"[fetcher] source={src.name} symbol={symbol} 返回空，尝试下一个源"
                )
                continue

            # 质量过滤
            cleaned, dropped = filter_dataframe(df, symbol, value_col='value')
            if dropped:
                logger.warning(
                    f"[fetcher] symbol={symbol} 源={src.name} 过滤掉 {dropped} 条异常值"
                )
            if cleaned is None or cleaned.empty:
                continue

            logger.info(
                f"[fetcher] symbol={symbol} 源={src.name} 取到 {len(cleaned)} 条"
            )
            return cleaned

        if last_error:
            logger.error(
                f"[fetcher] symbol={symbol} 所有源均失败，最后错误: {last_error}"
            )
        else:
            logger.warning(f"[fetcher] symbol={symbol} 没有任何源支持或返回数据")

        # 不抛异常，返回空 DataFrame，让 storage 层决定是否写入空记录
        return pd.DataFrame(columns=['date', 'value', 'publish_date'])

    # ------------------------------------------------------------------
    # 批量
    # ------------------------------------------------------------------

    def fetch_many(self, symbols: List[str], start_date: str, end_date: str) -> dict:
        """
        批量拉取，返回 {symbol: DataFrame}。
        """
        result = {}
        for sym in symbols:
            try:
                result[sym] = self.fetch(sym, start_date, end_date)
            except Exception as e:
                logger.error(f"[fetcher.fetch_many] {sym} 异常: {e}")
                result[sym] = pd.DataFrame(columns=['date', 'value', 'publish_date'])
        return result

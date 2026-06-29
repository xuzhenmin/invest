"""
宏观数据持久化层

设计要点：
- 表 ``macro_data`` 唯一键 (macro_symbol, date)，支持 INSERT OR REPLACE 增量更新
- 查询时按 ``publish_date <= as_of_date`` 过滤，严防前视偏差
- ``get_or_fetch`` 提供"先查库、缺则抓"的统一入口

表结构：
    macro_data
      - id            INTEGER PRIMARY KEY AUTOINCREMENT
      - macro_symbol  TEXT NOT NULL
      - date          TEXT NOT NULL          -- 数据期日 YYYY-MM-DD
      - value         REAL NOT NULL
      - publish_date  TEXT NOT NULL          -- 公布日 YYYY-MM-DD
      - source        TEXT
      - updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      - UNIQUE(macro_symbol, date)
"""

from typing import List, Optional

import pandas as pd

from service.storage.database_manager import db_manager
from utils.logger_config import get_logger

from .fetcher import MacroDataFetcher

logger = get_logger(__name__)


_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS macro_data (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    macro_symbol  TEXT NOT NULL,
    date          TEXT NOT NULL,
    value         REAL NOT NULL,
    publish_date  TEXT NOT NULL,
    source        TEXT,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(macro_symbol, date)
)
"""

_CREATE_INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_macro_symbol_date ON macro_data(macro_symbol, date)",
    "CREATE INDEX IF NOT EXISTS idx_macro_publish_date ON macro_data(macro_symbol, publish_date)",
]


class MacroDataStore:
    """宏观数据存储 + 增量抓取统一入口"""

    def __init__(self, fetcher: Optional[MacroDataFetcher] = None):
        self.fetcher = fetcher or MacroDataFetcher()
        self._ensure_table()

    # ------------------------------------------------------------------
    # 表初始化
    # ------------------------------------------------------------------

    def _ensure_table(self):
        if not db_manager.table_exists('macro_data'):
            db_manager.create_table(_CREATE_SQL)
            for sql in _CREATE_INDEX_SQL:
                db_manager.execute_update(sql)
            logger.info("[macro_storage] 创建 macro_data 表")

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def query(self, symbol: str, start_date: str, end_date: str,
              as_of_date: Optional[str] = None) -> pd.DataFrame:
        """
        从库中查询区间数据。

        Args:
            symbol: 宏观资产
            start_date / end_date: 数据期日区间
            as_of_date: 截止公布日（防前视）。None 表示不过滤。

        Returns:
            DataFrame[date, value, publish_date, source]，按 date 升序。
        """
        sql = (
            "SELECT date, value, publish_date, source FROM macro_data "
            "WHERE macro_symbol = ? AND date BETWEEN ? AND ?"
        )
        params = [symbol, start_date, end_date]
        if as_of_date:
            sql += " AND publish_date <= ?"
            params.append(as_of_date)
        sql += " ORDER BY date ASC"

        rows = db_manager.execute_query(sql, tuple(params))
        if not rows:
            return pd.DataFrame(columns=['date', 'value', 'publish_date', 'source'])
        return pd.DataFrame(rows)

    def get_latest_date(self, symbol: str) -> Optional[str]:
        """获取库中该 symbol 的最大数据期日。"""
        rows = db_manager.execute_query(
            "SELECT MAX(date) AS d FROM macro_data WHERE macro_symbol = ?",
            (symbol,),
        )
        if not rows:
            return None
        return rows[0].get('d')

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------

    def upsert(self, symbol: str, df: pd.DataFrame, source: str = 'unknown') -> int:
        """
        写入/覆盖区间数据，返回成功写入条数。
        """
        if df is None or df.empty:
            return 0

        required_cols = {'date', 'value', 'publish_date'}
        if not required_cols.issubset(df.columns):
            logger.warning(
                f"[macro_storage] upsert {symbol} 缺列: "
                f"need={required_cols}, got={set(df.columns)}"
            )
            return 0

        records = []
        for _, row in df.iterrows():
            records.append((
                symbol,
                row['date'],
                float(row['value']),
                row['publish_date'],
                source,
            ))

        sql = (
            "INSERT OR REPLACE INTO macro_data "
            "(macro_symbol, date, value, publish_date, source, updated_at) "
            "VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)"
        )
        affected = db_manager.execute_many(sql, records)
        logger.info(f"[macro_storage] upsert {symbol} 写入 {len(records)} 条")
        return affected

    # ------------------------------------------------------------------
    # 主入口：先查库、缺则抓
    # ------------------------------------------------------------------

    def get_or_fetch(self, symbol: str, start_date: str, end_date: str,
                     as_of_date: Optional[str] = None,
                     force_refresh: bool = False) -> pd.DataFrame:
        """
        先查库，若缺数据则增量抓取。

        Args:
            symbol: 宏观资产
            start_date / end_date: 期望区间
            as_of_date: 防前视的截止公布日
            force_refresh: True 时强制重新抓取整段区间

        Returns:
            DataFrame[date, value, publish_date, source]
        """
        if force_refresh:
            self._fetch_and_store(symbol, start_date, end_date)
            return self.query(symbol, start_date, end_date, as_of_date)

        latest = self.get_latest_date(symbol)
        if latest is None:
            # 库中无任何数据，整段抓
            self._fetch_and_store(symbol, start_date, end_date)
        elif latest < end_date:
            # 仅增量抓 latest+1 到 end_date
            incremental_start = (
                pd.to_datetime(latest) + pd.Timedelta(days=1)
            ).strftime('%Y-%m-%d')
            if incremental_start <= end_date:
                self._fetch_and_store(symbol, incremental_start, end_date)

        return self.query(symbol, start_date, end_date, as_of_date)

    def get_or_fetch_many(self, symbols: List[str], start_date: str, end_date: str,
                          as_of_date: Optional[str] = None) -> dict:
        """
        批量 get_or_fetch，返回 {symbol: DataFrame}。
        """
        return {
            sym: self.get_or_fetch(sym, start_date, end_date, as_of_date)
            for sym in symbols
        }

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _fetch_and_store(self, symbol: str, start_date: str, end_date: str) -> int:
        """抓取区间数据并写库，返回写入条数。"""
        df = self.fetcher.fetch(symbol, start_date, end_date)
        if df is None or df.empty:
            logger.info(f"[macro_storage] {symbol} {start_date}~{end_date} 无新数据")
            return 0
        # 找出实际生效的 source 名（fetcher 没回传，这里只能写入 'auto'）
        return self.upsert(symbol, df, source='auto')

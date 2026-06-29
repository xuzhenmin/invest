"""
新浪财经数据源

仅作为汇率类（USDCNH 等）的兜底，使用 akshare 提供的新浪聚合接口，
无需自己解析 HTML，兼顾稳定与轻量。
"""

import pandas as pd

from utils.logger_config import get_logger

from ..base import MacroDataError, MacroDataSource
from ..symbol_registry import MACRO_SYMBOL_MAP

logger = get_logger(__name__)


class SinaSource(MacroDataSource):
    """新浪财经兜底数据源（目前仅用于汇率）"""

    name = 'sina'
    priority = 30

    def __init__(self):
        self._ak = self._lazy_import_akshare()

    @staticmethod
    def _lazy_import_akshare():
        try:
            import akshare as ak  # type: ignore
            return ak
        except Exception:  # pragma: no cover
            return None

    def supports(self, symbol: str) -> bool:
        if self._ak is None:
            return False
        cfg = MACRO_SYMBOL_MAP.get(symbol)
        return bool(cfg and cfg.get('sina'))

    def fetch(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        if self._ak is None:
            raise MacroDataError("akshare(sina) 未安装", symbol=symbol, source=self.name)

        cfg = MACRO_SYMBOL_MAP.get(symbol)
        sina_symbol = cfg and cfg.get('sina')
        if not sina_symbol:
            return self.empty_df()

        try:
            # akshare 的 forex_hist_em / fx_spot_quote 等接口已覆盖大部分汇率
            # 这里复用 forex_spot_quote 取实时报价，历史走 fx_pair_quote/forex_hist_em
            func = getattr(self._ak, 'forex_hist_em', None)
            if func is None:
                raise MacroDataError("akshare 无 forex_hist_em", symbol=symbol, source=self.name)
            # 把内部 sina_symbol 转回 akshare 名称（这里做最小映射）
            ak_name = self._sina_to_akshare(sina_symbol)
            raw = func(symbol=ak_name)
        except Exception as e:
            logger.warning(f"[sina] fetch {symbol} 失败: {e}")
            raise MacroDataError(str(e), symbol=symbol, source=self.name) from e

        if raw is None or raw.empty:
            return self.empty_df()

        date_col = '日期' if '日期' in raw.columns else 'date'
        value_col = None
        for c in ('收盘价', '最新价', '今开', 'close'):
            if c in raw.columns:
                value_col = c
                break
        if value_col is None:
            return self.empty_df()

        out = self.normalize_df(raw, date_col=date_col, value_col=value_col)
        out = out[(out['date'] >= start_date) & (out['date'] <= end_date)].reset_index(drop=True)
        return out

    @staticmethod
    def _sina_to_akshare(sina_symbol: str) -> str:
        """新浪汇率代码 → akshare forex_hist_em 名称的最小映射"""
        mapping = {
            'fx_susdcnh': '美元人民币',
        }
        return mapping.get(sina_symbol, sina_symbol)

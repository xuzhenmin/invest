"""
yfinance 数据源

兜底美股 / 美债 / 商品类资产。当 akshare 接口不可用或字段变更时使用。
仅支持 ``MACRO_SYMBOL_MAP`` 中配置了 ``yfinance`` 字段的 symbol。
"""

import time

import pandas as pd

from utils.logger_config import get_logger

from ..base import MacroDataError, MacroDataSource
from ..symbol_registry import MACRO_SYMBOL_MAP

logger = get_logger(__name__)

# 模块级别的请求时间戳，用于全局限流控制
_last_request_time: float = 0.0
_MIN_REQUEST_INTERVAL: float = 2.0  # 每次请求最少间隔2秒


class YFinanceSource(MacroDataSource):
    """yfinance 兜底数据源（含限流防护）"""

    name = 'yfinance'
    priority = 50
    _MAX_RETRIES = 3
    _RETRY_BACKOFF = [3.0, 6.0, 12.0]  # 重试退避时间

    def __init__(self):
        self._yf = self._lazy_import_yfinance()

    @staticmethod
    def _lazy_import_yfinance():
        try:
            import yfinance as yf  # type: ignore
            return yf
        except Exception as e:  # pragma: no cover
            logger.warning(f"yfinance 不可用: {e}")
            return None

    def supports(self, symbol: str) -> bool:
        if self._yf is None:
            return False
        cfg = MACRO_SYMBOL_MAP.get(symbol)
        return bool(cfg and cfg.get('yfinance'))

    @staticmethod
    def _throttle():
        """全局限流：确保两次请求间隔至少 _MIN_REQUEST_INTERVAL 秒。"""
        global _last_request_time
        now = time.monotonic()
        elapsed = now - _last_request_time
        if elapsed < _MIN_REQUEST_INTERVAL:
            time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
        _last_request_time = time.monotonic()

    def _download_with_retry(self, ticker: str, start_date: str, end_plus: str,
                             symbol: str) -> pd.DataFrame:
        """带重试和退避的 yfinance.download 封装。"""
        last_error = None
        for attempt in range(self._MAX_RETRIES):
            self._throttle()
            try:
                raw = self._yf.download(
                    ticker,
                    start=start_date,
                    end=end_plus,
                    progress=False,
                    auto_adjust=False,
                    threads=False,
                )
                if raw is not None and not raw.empty:
                    return raw
                # 空结果也可能是限流导致，重试
                if attempt < self._MAX_RETRIES - 1:
                    backoff = self._RETRY_BACKOFF[attempt]
                    logger.info(f"[yfinance] {ticker} 第{attempt + 1}次返回空，{backoff}s后重试")
                    time.sleep(backoff)
            except Exception as e:
                last_error = e
                if attempt < self._MAX_RETRIES - 1:
                    backoff = self._RETRY_BACKOFF[attempt]
                    logger.info(f"[yfinance] {ticker} 第{attempt + 1}次失败({e})，{backoff}s后重试")
                    time.sleep(backoff)
                else:
                    raise MacroDataError(str(e), symbol=symbol, source=self.name) from e

        if last_error:
            raise MacroDataError(str(last_error), symbol=symbol, source=self.name)
        return pd.DataFrame()

    def fetch(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        if self._yf is None:
            raise MacroDataError("yfinance 未安装", symbol=symbol, source=self.name)

        cfg = MACRO_SYMBOL_MAP.get(symbol)
        ticker = cfg and cfg.get('yfinance')
        if not ticker:
            return self.empty_df()

        # yfinance 的 end 参数是开区间，需要 +1 天
        end_plus = (pd.to_datetime(end_date) + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
        raw = self._download_with_retry(ticker, start_date, end_plus, symbol)

        if raw is None or raw.empty:
            return self.empty_df()

        # yfinance 返回 MultiIndex columns 的兼容处理
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = [c[0] for c in raw.columns]

        if 'Close' not in raw.columns:
            return self.empty_df()

        out = pd.DataFrame({
            'date': pd.to_datetime(raw.index).strftime('%Y-%m-%d'),
            'value': pd.to_numeric(raw['Close'], errors='coerce'),
        })
        out['publish_date'] = out['date']
        out = out.dropna(subset=['value']).reset_index(drop=True)
        return out

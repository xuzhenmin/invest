"""
金融数据 API 数据源

使用 FinancialDataClient 获取宏观数据，作为 akshare/yfinance 的高优先级替代，
提供更稳定、更标准化的数据获取能力。

支持两类 symbol：

国内宏观月度指标（月频，需用 publish_calendar 估算 publish_date）：
- CPI_YOY   → get_cpi()
- PPI_YOY   → get_ppi()
- PMI_MFG   → get_pmi(category='manufacturing')
- PMI_NMFG  → get_pmi(category='non_manufacturing')

全球市场日频指标（日频，publish_date = date）：
- VIX       → get_vix()
- GOLD      → get_gold_price()
- COPPER    → get_copper_price()
- DXY       → get_dxy()
- BRENT     → get_brent_oil()
- WTI       → get_wti_oil()
- USDCNH    → get_usdcnh()
- HSI       → get_hsi()
"""

import pandas as pd

from utils.logger_config import get_logger

from ..base import MacroDataError, MacroDataSource
from ..publish_calendar import fill_publish_date

logger = get_logger(__name__)

# symbol → FinancialDataClient 调用参数映射
# is_monthly=True 的 symbol 使用 publish_calendar 估算 publish_date
# is_monthly=False 的 symbol publish_date 直接等于 date
_SYMBOL_FETCH_CONFIG = {
    # ---------- 国内宏观月度 ----------
    'CPI_YOY': {
        'method': 'get_cpi',
        'kwargs': {'period': 'monthly', 'years': 5},
        'is_monthly': True,
    },
    'PPI_YOY': {
        'method': 'get_ppi',
        'kwargs': {'period': 'monthly', 'years': 5},
        'is_monthly': True,
    },
    'PMI_MFG': {
        'method': 'get_pmi',
        'kwargs': {'category': 'manufacturing', 'years': 5},
        'is_monthly': True,
    },
    'PMI_NMFG': {
        'method': 'get_pmi',
        'kwargs': {'category': 'non_manufacturing', 'years': 5},
        'is_monthly': True,
    },
    # ---------- 全球市场日频 ----------
    'VIX': {
        'method': 'get_vix',
        'kwargs': {'years': 3},
        'is_monthly': False,
    },
    'GOLD': {
        'method': 'get_gold_price',
        'kwargs': {'years': 3},
        'is_monthly': False,
    },
    'COPPER': {
        'method': 'get_copper_price',
        'kwargs': {'years': 3},
        'is_monthly': False,
    },
    'DXY': {
        'method': 'get_dxy',
        'kwargs': {'years': 3},
        'is_monthly': False,
    },
    'BRENT': {
        'method': 'get_brent_oil',
        'kwargs': {'years': 3},
        'is_monthly': False,
    },
    'WTI': {
        'method': 'get_wti_oil',
        'kwargs': {'years': 3},
        'is_monthly': False,
    },
    'USDCNH': {
        'method': 'get_usdcnh',
        'kwargs': {'years': 3},
        'is_monthly': False,
    },
    'HSI': {
        'method': 'get_hsi',
        'kwargs': {'years': 3},
        'is_monthly': False,
    },
}


class FinancialApiSource(MacroDataSource):
    """基于 FinancialDataClient 的宏观数据源（优先级高于 akshare）"""

    name = 'financial_api'
    priority = 5  # 高于 akshare(10)，优先使用

    def __init__(self):
        self._client = None
        self._init_error = None

    def _get_client(self):
        """惰性初始化 FinancialDataClient，避免导入时就报错。"""
        if self._client is not None:
            return self._client
        if self._init_error is not None:
            return None
        try:
            from service.datapip.financial_data_client import FinancialDataClient
            self._client = FinancialDataClient()
            return self._client
        except Exception as exc:
            self._init_error = exc
            logger.warning(f"[financial_api] FinancialDataClient 初始化失败: {exc}")
            return None

    def supports(self, symbol: str) -> bool:
        return symbol in _SYMBOL_FETCH_CONFIG and self._get_client() is not None

    def fetch(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        client = self._get_client()
        if client is None:
            raise MacroDataError(
                "FinancialDataClient 不可用", symbol=symbol, source=self.name,
            )

        config = _SYMBOL_FETCH_CONFIG.get(symbol)
        if config is None:
            return self.empty_df()

        method_name = config['method']
        kwargs = dict(config['kwargs'])

        try:
            api_method = getattr(client, method_name)
            raw_response = api_method(**kwargs)
        except Exception as exc:
            raise MacroDataError(
                f"API 调用 {method_name} 失败: {exc}",
                symbol=symbol, source=self.name,
            ) from exc

        is_monthly = config.get('is_monthly', False)
        dataframe = self._parse_response(raw_response, symbol, is_monthly)

        if dataframe.empty:
            return self.empty_df()

        # 按请求区间过滤
        dataframe = dataframe[
            (dataframe['date'] >= start_date) & (dataframe['date'] <= end_date)
        ].reset_index(drop=True)

        return dataframe

    def _parse_response(self, response: dict, symbol: str,
                        is_monthly: bool = False) -> pd.DataFrame:
        """将 FinancialDataClient 返回的时间序列响应解析为标准 DataFrame。

        API 返回格式（命名时间序列）：
        {
            "results": [
                {"meta": {"name": "CPI:同比:月", "unit": "%"},
                 "data": {"2024-01-31 00:00:00": 0.8, ...}}
            ]
        }

        Args:
            response: API 原始响应
            symbol: 宏观资产 symbol
            is_monthly: 是否为月频数据，True 时使用 publish_calendar 估算 publish_date
        """
        if not isinstance(response, dict):
            logger.warning(f"[financial_api] {symbol} 响应格式异常: 非 dict")
            return self.empty_df()

        results = response.get('results', [])
        if not isinstance(results, list) or not results:
            logger.warning(f"[financial_api] {symbol} 无有效 results")
            return self.empty_df()

        all_records = []
        for series in results:
            if not isinstance(series, dict):
                continue
            data = series.get('data', {})
            if not isinstance(data, dict):
                continue
            for date_str, value in data.items():
                if value is None:
                    continue
                # 日期标准化：去掉时间部分
                normalized_date = date_str.split(' ')[0] if ' ' in date_str else date_str
                all_records.append({
                    'date': normalized_date,
                    'value': float(value),
                })

        if not all_records:
            return self.empty_df()

        dataframe = pd.DataFrame(all_records)
        dataframe['date'] = pd.to_datetime(dataframe['date'], errors='coerce').dt.strftime('%Y-%m-%d')
        dataframe = dataframe.dropna(subset=['date', 'value']).copy()
        dataframe = dataframe.sort_values('date').drop_duplicates(subset=['date'], keep='last').reset_index(drop=True)

        if is_monthly:
            # 月频数据用 publish_calendar 估算 publish_date（防前视偏差）
            dataframe['publish_date'] = dataframe['date']
            dataframe = fill_publish_date(dataframe, symbol, period_col='date')
        else:
            # 日频数据 publish_date = date（实时可用）
            dataframe['publish_date'] = dataframe['date']

        return dataframe

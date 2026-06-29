"""
akshare 数据源

主力数据源，覆盖：
- 货币：DXY / USDCNH
- 利率：UST10Y / UST2Y / CN10Y
- 大宗：BRENT / WTI / GOLD / COPPER / SH_COPPER
- 股指期货：IF/IC/IH 主连
- 股指现货：HS300 / ZZ500 / SZ50
- 风险偏好：VIX / SPX / DJI / IXIC / HSI
- 国内宏观月度：PMI / CPI / PPI / M2 / 社融

设计原则：
- akshare 接口名/字段易变，所有调用包 try/except，单 symbol 失败不影响其他
- 区分日频与月频，月频统一调用 publish_calendar.fill_publish_date
- 标准结构由 base.MacroDataSource.normalize_df 统一保证
"""

from typing import Optional

import pandas as pd

from utils.logger_config import get_logger

from ..base import MacroDataError, MacroDataSource
from ..publish_calendar import fill_publish_date
from ..symbol_registry import MACRO_SYMBOL_MAP, is_monthly

logger = get_logger(__name__)


class AkshareSource(MacroDataSource):
    """akshare 数据源实现"""

    name = 'akshare'
    priority = 10

    def __init__(self):
        self._ak = self._lazy_import_akshare()

    @staticmethod
    def _lazy_import_akshare():
        """惰性导入，避免在没装 akshare 时整个模块崩溃。"""
        try:
            import akshare as ak  # type: ignore
            return ak
        except Exception as e:  # pragma: no cover
            logger.warning(f"akshare 不可用: {e}")
            return None

    # ------------------------------------------------------------------
    # MacroDataSource 接口
    # ------------------------------------------------------------------

    def supports(self, symbol: str) -> bool:
        if self._ak is None:
            return False
        cfg = MACRO_SYMBOL_MAP.get(symbol)
        return bool(cfg and 'akshare' in cfg)

    def fetch(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        if self._ak is None:
            raise MacroDataError("akshare 未安装", symbol=symbol, source=self.name)

        cfg = MACRO_SYMBOL_MAP.get(symbol)
        if not cfg or 'akshare' not in cfg:
            return self.empty_df()

        category = cfg.get('category')
        try:
            if is_monthly(symbol):
                df = self._fetch_monthly(symbol, cfg)
            elif category == 'currency':
                df = self._fetch_currency(symbol, cfg)
            elif category == 'rates':
                df = self._fetch_rates(symbol, cfg)
            elif category == 'commodity':
                df = self._fetch_commodity(symbol, cfg)
            elif category == 'futures':
                df = self._fetch_futures(symbol, cfg)
            elif category == 'index':
                df = self._fetch_index(symbol, cfg)
            elif category == 'risk':
                df = self._fetch_risk(symbol, cfg)
            else:
                logger.warning(f"[akshare] 未识别的 category={category}, symbol={symbol}")
                return self.empty_df()
        except Exception as e:
            logger.warning(f"[akshare] fetch {symbol} 失败: {e}")
            raise MacroDataError(str(e), symbol=symbol, source=self.name) from e

        if df is None or df.empty:
            return self.empty_df()

        # 区间过滤
        df = df[(df['date'] >= start_date) & (df['date'] <= end_date)].reset_index(drop=True)
        return df

    # ------------------------------------------------------------------
    # 各 category 拉取实现
    # ------------------------------------------------------------------

    def _fetch_currency(self, symbol: str, cfg: dict) -> pd.DataFrame:
        """货币：美元指数 / USDCNH（支持 currency_boc_sina 和 forex_hist_em）"""
        ak_cfg = cfg['akshare']
        func_name = ak_cfg['func']
        params = ak_cfg.get('params', {})
        func = getattr(self._ak, func_name, None)
        if func is None:
            raise MacroDataError(f"akshare 无 {func_name}", symbol=symbol, source=self.name)
        raw = func(**params)

        # currency_boc_sina 返回: ['日期','中行汇买价','中行钞买价','中行钞卖价/汇卖价','央行中间价','中行折算价']
        # forex_hist_em 返回: ['日期','今开','最新价','最高','最低','成交量','振幅','涨跌幅','涨跌额']
        explicit_value_col = ak_cfg.get('value_col')
        date_col = self._pick_col(raw, ['date', '日期'])
        if explicit_value_col and explicit_value_col in raw.columns:
            value_col = explicit_value_col
        else:
            value_col = self._pick_col(raw, ['close', '收盘价', '最新价', '今开',
                                              '央行中间价', '中行折算价'])
        return self.normalize_df(raw, date_col=date_col, value_col=value_col)

    def _fetch_rates(self, symbol: str, cfg: dict) -> pd.DataFrame:
        """利率：bond_zh_us_rate 一次返回中美 2/10 年收益率，按 value_col 取列"""
        ak_cfg = cfg['akshare']
        func_name = ak_cfg['func']
        value_col_zh = ak_cfg['value_col']
        func = getattr(self._ak, func_name, None)
        if func is None:
            raise MacroDataError(f"akshare 无 {func_name}", symbol=symbol, source=self.name)
        raw = func()
        date_col = self._pick_col(raw, ['日期', 'date'])
        if value_col_zh not in raw.columns:
            raise MacroDataError(
                f"列 {value_col_zh} 不存在于 {func_name} 返回结果",
                symbol=symbol, source=self.name,
            )
        return self.normalize_df(raw, date_col=date_col, value_col=value_col_zh)

    def _fetch_commodity(self, symbol: str, cfg: dict) -> pd.DataFrame:
        """大宗商品：境外原油/黄金/铜 + 境内沪铜"""
        ak_cfg = cfg['akshare']
        func_name = ak_cfg['func']
        params = ak_cfg.get('params', {})
        func = getattr(self._ak, func_name, None)
        if func is None:
            raise MacroDataError(f"akshare 无 {func_name}", symbol=symbol, source=self.name)
        raw = func(**params)
        date_col = self._pick_col(raw, ['date', '日期'])
        value_col = self._pick_col(raw, ['close', '收盘价', '收盘'])
        return self.normalize_df(raw, date_col=date_col, value_col=value_col)

    def _fetch_futures(self, symbol: str, cfg: dict) -> pd.DataFrame:
        """国内股指期货主连"""
        ak_cfg = cfg['akshare']
        func_name = ak_cfg['func']
        params = ak_cfg.get('params', {})
        func = getattr(self._ak, func_name, None)
        if func is None:
            raise MacroDataError(f"akshare 无 {func_name}", symbol=symbol, source=self.name)
        raw = func(**params)
        date_col = self._pick_col(raw, ['date', '日期'])
        value_col = self._pick_col(raw, ['close', '收盘价', '收盘'])
        return self.normalize_df(raw, date_col=date_col, value_col=value_col)

    def _fetch_index(self, symbol: str, cfg: dict) -> pd.DataFrame:
        """A 股股指现货"""
        ak_cfg = cfg['akshare']
        func_name = ak_cfg['func']
        params = ak_cfg.get('params', {})
        func = getattr(self._ak, func_name, None)
        if func is None:
            raise MacroDataError(f"akshare 无 {func_name}", symbol=symbol, source=self.name)
        raw = func(**params)
        date_col = self._pick_col(raw, ['date', '日期'])
        value_col = self._pick_col(raw, ['close', '收盘价', '收盘'])
        return self.normalize_df(raw, date_col=date_col, value_col=value_col)

    def _fetch_risk(self, symbol: str, cfg: dict) -> pd.DataFrame:
        """美股 + 港股 + VIX"""
        ak_cfg = cfg['akshare']
        func_name = ak_cfg['func']
        params = ak_cfg.get('params', {})
        func = getattr(self._ak, func_name, None)
        if func is None:
            raise MacroDataError(f"akshare 无 {func_name}", symbol=symbol, source=self.name)
        raw = func(**params)
        date_col = self._pick_col(raw, ['date', '日期'])
        value_col = self._pick_col(raw, ['close', '收盘价', '收盘'])
        return self.normalize_df(raw, date_col=date_col, value_col=value_col)

    def _fetch_monthly(self, symbol: str, cfg: dict) -> pd.DataFrame:
        """国内宏观月度数据"""
        ak_cfg = cfg['akshare']
        func_name = ak_cfg['func']
        func = getattr(self._ak, func_name, None)
        if func is None:
            raise MacroDataError(f"akshare 无 {func_name}", symbol=symbol, source=self.name)
        raw = func()

        # 不同接口返回字段差异较大，做兜底匹配
        date_col = self._pick_col(raw, ['日期', 'date', '月份', '统计月份'])
        value_col = self._pick_col(
            raw,
            ['今值', 'value', '现值', '同比增长', '同比', '今值(%)', '当月同比'],
        )
        df = self.normalize_df(raw, date_col=date_col, value_col=value_col)
        # 月度数据 publish_date 用次月偏移估算
        df = fill_publish_date(df, symbol, period_col='date')
        return df

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------

    @staticmethod
    def _pick_col(df: pd.DataFrame, candidates) -> Optional[str]:
        """从候选列名里挑一个真实存在的，找不到则返回第一个候选（让上层报错信息更清晰）。"""
        for c in candidates:
            if c in df.columns:
                return c
        return candidates[0]

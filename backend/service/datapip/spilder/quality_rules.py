"""
宏观数据质量校验规则

抓取后立即校验，异常值不入库；既能挡住爬虫解析错误，
也能对原始数据源跳点做基础保护。
"""

from typing import Callable, Dict


# 每个 symbol 的合理值域 (min, max)
QUALITY_RANGES: Dict[str, tuple] = {
    # 货币
    'DXY':        (60, 130),
    'USDCNH':     (5, 9),

    # 利率（单位 %）
    'UST10Y':     (-1, 15),
    'UST2Y':      (-1, 15),
    'CN10Y':      (0, 10),

    # 大宗
    'BRENT':      (10, 200),
    'WTI':        (-50, 200),    # 2020 年负油价历史
    'GOLD':       (800, 4000),
    'COPPER':     (1, 8),         # USD/lb
    'SH_COPPER':  (20000, 120000),  # CNY/吨

    # 股指期货（点位）
    'IF_FRONT':   (1500, 8000),
    'IC_FRONT':   (3000, 12000),
    'IH_FRONT':   (1500, 5000),
    'HS300_SPOT': (1500, 8000),
    'ZZ500_SPOT': (3000, 12000),
    'SZ50_SPOT':  (1500, 5000),

    # 风险偏好
    'VIX':        (5, 100),
    'SPX':        (1000, 10000),
    'DJI':        (8000, 60000),
    'IXIC':       (1000, 30000),
    'HSI':        (10000, 50000),

    # 国内宏观
    'PMI_MFG':    (30, 70),
    'PMI_NMFG':   (30, 70),
    'CPI_YOY':    (-10, 30),
    'PPI_YOY':    (-15, 30),
    'M2_YOY':     (0, 50),
    'SOCIAL_FIN': (-20, 50),
}


def validate(symbol: str, value: float) -> bool:
    """
    校验单个数值是否在合理区间内。

    未配置规则的 symbol 默认通过（保守策略，避免误拦）。
    """
    rng = QUALITY_RANGES.get(symbol)
    if rng is None:
        return True
    if value is None:
        return False
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False
    return rng[0] <= v <= rng[1]


def filter_dataframe(df, symbol: str, value_col: str = 'value'):
    """
    过滤 DataFrame 中不合规的行，返回 (cleaned_df, dropped_count)。
    """
    if df is None or df.empty or value_col not in df.columns:
        return df, 0

    rule: Callable[[float], bool] = lambda v: validate(symbol, v)
    mask = df[value_col].apply(rule)
    dropped = int((~mask).sum())
    return df[mask].reset_index(drop=True), dropped

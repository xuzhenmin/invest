"""
宏观月度数据公布日校正

对没有原生 publish_date 字段的 akshare 接口，按经验规则估计公布日，
确保因子查询时能用 ``publish_date <= trade_date`` 严防前视偏差。
"""

import pandas as pd


# 各类月度数据的"次月公布日偏移"（自然日）
# 取保守值（最晚公布日 + 缓冲），宁可晚一两天用上，绝不能提前
MONTHLY_PUBLISH_OFFSET_DAYS = {
    'PMI_MFG':    1,    # 制造业 PMI: 次月 1 号上午 9:30
    'PMI_NMFG':   3,    # 非制造业 PMI: 次月初
    'CPI_YOY':    16,   # CPI: 次月 9-15 号
    'PPI_YOY':    16,   # PPI: 次月 9-15 号
    'M2_YOY':     16,   # M2: 次月 10-15 号
    'SOCIAL_FIN': 16,   # 社融: 次月 10-15 号
}

# 默认偏移（未在表中的月度数据）
DEFAULT_MONTHLY_OFFSET_DAYS = 16


def estimate_publish_date(symbol: str, period_date: pd.Timestamp) -> pd.Timestamp:
    """
    根据统计期日期估算公布日。

    Args:
        symbol: 宏观资产 symbol（用于查偏移天数）
        period_date: 统计期（如 2024-03-01 表示 3 月数据）

    Returns:
        估算的公布日 Timestamp（即 ``次月月初 + offset_days``）
    """
    if pd.isna(period_date):
        return period_date

    period_dt = pd.Timestamp(period_date)
    # 统一对齐到当月月初
    month_start = period_dt.replace(day=1)
    # 次月月初
    next_month_start = month_start + pd.offsets.MonthBegin(1)
    offset = MONTHLY_PUBLISH_OFFSET_DAYS.get(symbol, DEFAULT_MONTHLY_OFFSET_DAYS)
    return next_month_start + pd.Timedelta(days=offset)


def fill_publish_date(df: pd.DataFrame, symbol: str,
                      period_col: str = 'date') -> pd.DataFrame:
    """
    给月度数据 DataFrame 填充 publish_date 列。

    Args:
        df: 含 ``period_col`` 的 DataFrame
        symbol: 宏观资产 symbol
        period_col: 统计期列名（默认 'date'）

    Returns:
        新增/覆盖了 ``publish_date`` 列的 DataFrame（不修改原对象）
    """
    if df is None or df.empty:
        return df

    out = df.copy()
    period_dates = pd.to_datetime(out[period_col], errors='coerce')
    out['publish_date'] = period_dates.apply(
        lambda d: estimate_publish_date(symbol, d)
    ).dt.strftime('%Y-%m-%d')
    return out

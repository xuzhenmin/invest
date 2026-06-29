"""
宏观资产 Symbol 注册表

定义统一的 macro_symbol → 各数据源具体 ID 的映射，
让因子代码只需引用 ``DXY`` / ``UST10Y`` / ``IF_FRONT`` 等业务名，
不用关心具体源的 API 细节。
"""

from typing import Dict


# ============================================================
# 业务 symbol 定义（按品类分组）
# ============================================================

# 日频资产
DAILY_SYMBOLS = (
    # 货币
    'DXY', 'USDCNH',
    # 利率
    'UST10Y', 'UST2Y', 'CN10Y',
    # 大宗
    'BRENT', 'WTI', 'GOLD', 'COPPER', 'SH_COPPER',
    # 股指期货
    'IF_FRONT', 'IC_FRONT', 'IH_FRONT',
    # 股指现货（基差因子需要）
    'HS300_SPOT', 'ZZ500_SPOT', 'SZ50_SPOT',
    # 风险偏好
    'VIX', 'SPX', 'DJI', 'IXIC', 'HSI',
)

# 月频资产
MONTHLY_SYMBOLS = (
    'PMI_MFG',     # 制造业 PMI
    'PMI_NMFG',    # 非制造业 PMI
    'CPI_YOY',     # CPI 同比
    'PPI_YOY',     # PPI 同比
    'M2_YOY',      # M2 同比
    'SOCIAL_FIN',  # 社会融资规模存量同比
)


# ============================================================
# Symbol → 各数据源 ID 映射
# 每条记录: {
#   'akshare': dict | str | tuple,   # akshare 拉取参数
#   'yfinance': str,                 # yfinance ticker
#   'sina': str,                     # 新浪 hq 接口 symbol
#   'category': 'currency' | 'rates' | 'commodity' | 'futures' | 'index' | 'macro_cn',
#   'is_monthly': bool,              # 是否月频
#   'description': str,
# }
# ============================================================

MACRO_SYMBOL_MAP: Dict[str, dict] = {
    # ---------- 货币 ----------
    'DXY': {
        'category': 'currency',
        'description': '美元指数 ICE（via FinancialApiSource）',
    },
    'USDCNH': {
        'category': 'currency',
        'description': '离岸人民币（via FinancialApiSource）',
    },

    # ---------- 利率 ----------
    'UST10Y': {
        'akshare': {'func': 'bond_zh_us_rate', 'value_col': '美国国债收益率10年'},
        'yfinance': '^TNX',
        'category': 'rates',
        'description': '美债 10 年期收益率',
    },
    'UST2Y': {
        'akshare': {'func': 'bond_zh_us_rate', 'value_col': '美国国债收益率2年'},
        'yfinance': '^IRX',  # 注意 ^IRX 是 13 周，最接近的 2Y 无统一免费源
        'category': 'rates',
        'description': '美债 2 年期收益率',
    },
    'CN10Y': {
        'akshare': {'func': 'bond_zh_us_rate', 'value_col': '中国国债收益率10年'},
        'category': 'rates',
        'description': '中债 10 年期收益率',
    },

    # ---------- 大宗 ----------
    'BRENT': {
        'category': 'commodity',
        'description': '布伦特原油 (ICE)（via FinancialApiSource）',
    },
    'WTI': {
        'category': 'commodity',
        'description': 'WTI 原油 (NYMEX)（via FinancialApiSource）',
    },
    'GOLD': {
        'category': 'commodity',
        'description': 'COMEX 黄金（via FinancialApiSource）',
    },
    'COPPER': {
        'category': 'commodity',
        'description': 'COMEX 铜（via FinancialApiSource）',
    },
    'SH_COPPER': {
        'akshare': {'func': 'futures_zh_daily_sina', 'params': {'symbol': 'cu0'}},
        'category': 'commodity',
        'description': '沪铜主连',
    },

    # ---------- 股指期货 ----------
    'IF_FRONT': {
        'akshare': {'func': 'futures_zh_daily_sina', 'params': {'symbol': 'IF0'}},
        'category': 'futures',
        'description': '沪深 300 股指期货主连',
    },
    'IC_FRONT': {
        'akshare': {'func': 'futures_zh_daily_sina', 'params': {'symbol': 'IC0'}},
        'category': 'futures',
        'description': '中证 500 股指期货主连',
    },
    'IH_FRONT': {
        'akshare': {'func': 'futures_zh_daily_sina', 'params': {'symbol': 'IH0'}},
        'category': 'futures',
        'description': '上证 50 股指期货主连',
    },

    # ---------- 股指现货 ----------
    'HS300_SPOT': {
        'akshare': {'func': 'stock_zh_index_daily', 'params': {'symbol': 'sh000300'}},
        'category': 'index',
        'description': '沪深 300 现货指数',
    },
    'ZZ500_SPOT': {
        'akshare': {'func': 'stock_zh_index_daily', 'params': {'symbol': 'sh000905'}},
        'category': 'index',
        'description': '中证 500 现货指数',
    },
    'SZ50_SPOT': {
        'akshare': {'func': 'stock_zh_index_daily', 'params': {'symbol': 'sh000016'}},
        'category': 'index',
        'description': '上证 50 现货指数',
    },

    # ---------- 风险偏好 ----------
    'VIX': {
        'category': 'risk',
        'description': 'CBOE 波动率指数（via FinancialApiSource）',
    },
    'SPX': {
        'akshare': {'func': 'index_us_stock_sina', 'params': {'symbol': '.INX'}},
        'yfinance': '^GSPC',
        'category': 'risk',
        'description': '标普 500',
    },
    'DJI': {
        'akshare': {'func': 'index_us_stock_sina', 'params': {'symbol': '.DJI'}},
        'yfinance': '^DJI',
        'category': 'risk',
        'description': '道琼斯工业平均',
    },
    'IXIC': {
        'akshare': {'func': 'index_us_stock_sina', 'params': {'symbol': '.IXIC'}},
        'yfinance': '^IXIC',
        'category': 'risk',
        'description': '纳斯达克综合',
    },
    'HSI': {
        'category': 'risk',
        'description': '恒生指数（via FinancialApiSource）',
    },

    # ---------- 国内宏观月度 ----------
    'PMI_MFG': {
        'akshare': {'func': 'macro_china_pmi_yearly'},
        'is_monthly': True,
        'category': 'macro_cn',
        'description': '中国制造业 PMI',
    },
    'PMI_NMFG': {
        'akshare': {'func': 'macro_china_non_man_pmi'},
        'is_monthly': True,
        'category': 'macro_cn',
        'description': '中国非制造业 PMI',
    },
    'CPI_YOY': {
        'akshare': {'func': 'macro_china_cpi_yearly'},
        'is_monthly': True,
        'category': 'macro_cn',
        'description': '中国 CPI 同比',
    },
    'PPI_YOY': {
        'akshare': {'func': 'macro_china_ppi_yearly'},
        'is_monthly': True,
        'category': 'macro_cn',
        'description': '中国 PPI 同比',
    },
    'M2_YOY': {
        'akshare': {'func': 'macro_china_m2_yearly'},
        'is_monthly': True,
        'category': 'macro_cn',
        'description': '中国 M2 同比',
    },
    'SOCIAL_FIN': {
        'akshare': {'func': 'macro_china_shrzgm'},
        'is_monthly': True,
        'category': 'macro_cn',
        'description': '中国社融存量同比',
    },
}


# ============================================================
# 工具函数
# ============================================================

def is_monthly(symbol: str) -> bool:
    """判断 symbol 是否为月频。"""
    cfg = MACRO_SYMBOL_MAP.get(symbol)
    return bool(cfg and cfg.get('is_monthly', False))


def get_config(symbol: str) -> dict:
    """获取 symbol 的完整配置。"""
    cfg = MACRO_SYMBOL_MAP.get(symbol)
    if cfg is None:
        raise KeyError(f"Unknown macro symbol: {symbol}")
    return cfg


def list_symbols(category: str = None, monthly_only: bool = None) -> list:
    """按品类 / 频率筛选 symbol。"""
    result = []
    for sym, cfg in MACRO_SYMBOL_MAP.items():
        if category and cfg.get('category') != category:
            continue
        if monthly_only is True and not cfg.get('is_monthly'):
            continue
        if monthly_only is False and cfg.get('is_monthly'):
            continue
        result.append(sym)
    return result

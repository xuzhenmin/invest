"""
数据模型定义
定义交易相关的数据表结构
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

class OrderStatus(Enum):
    """订单状态枚举"""
    PENDING = "pending"
    EXECUTED = "executed"
    CANCELLED = "cancelled"
    FAILED = "failed"

class TradeDirection(Enum):
    """交易方向枚举"""
    BUY = "buy"
    SELL = "sell"

class PositionStatus(Enum):
    """持仓状态枚举"""
    ACTIVE = "active"      # 活跃持仓
    PARTIAL_SOLD = "partial_sold"  # 部分卖出
    CLOSED = "closed"      # 已清仓
    CANCELLED = "cancelled"  # 已取消

class RiskLevel(Enum):
    """风险等级枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class Recommendation(Enum):
    """投资建议枚举"""
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"

@dataclass
class StockInfo:
    """股票基本信息"""
    code: str
    name: str
    market: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class TradeRecord:
    """交易记录"""
    id: Optional[int] = None
    user_id: str = ""
    symbol: str = ""
    name: str = ""
    action: str = ""
    timestamp: Optional[datetime] = None
    trade_date: Optional[datetime] = None
    price: float = 0.0
    quantity: int = 0
    total_cost: float = 0.0
    order_id: Optional[str] = None
    signal_data: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None

@dataclass
class Position:
    """持仓信息"""
    id: Optional[int] = None
    user_id: str = ""
    symbol: str = ""
    name: str = ""
    quantity: int = 0
    avg_price: float = 0.0
    total_cost: float = 0.0
    market_value: float = 0.0
    floating_pnl: float = 0.0
    floating_pnl_ratio: float = 0.0
    last_price: float = 0.0
    updated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

@dataclass
class StrategySignal:
    """策略信号"""
    id: Optional[int] = None
    strategy_name: str = ""
    stock_code: str = ""
    signal_type: str = ""  # buy/sell/hold
    signal_strength: float = 0.0
    signal_date: Optional[datetime] = None
    parameters: Optional[Dict[str, Any]] = None
    executed: bool = False
    created_at: Optional[datetime] = None

@dataclass
class MarketData:
    """市场数据"""
    id: Optional[int] = None
    stock_code: str = ""
    trade_date: Optional[datetime] = None
    open_price: float = 0.0
    high_price: float = 0.0
    low_price: float = 0.0
    close_price: float = 0.0
    volume: int = 0
    turnover: float = 0.0
    created_at: Optional[datetime] = None

@dataclass
class DiagnosisReport:
    """诊断报告"""
    id: Optional[int] = None
    symbol: str = ""
    date: Optional[datetime] = None
    name: str = ""
    current_price: float = 0.0
    overall_score: float = 0.0
    fundamental_score: float = 0.0
    technical_score: float = 0.0
    capital_score: float = 0.0
    valuation_score: float = 0.0
    risk_level: str = RiskLevel.MEDIUM.value
    recommendation: str = Recommendation.HOLD.value
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    support: Optional[float] = None
    resistance: Optional[float] = None
    buy_price: Optional[float] = None
    sell_price: Optional[float] = None
    investment_reason: str = ""
    key_indicators: Optional[list] = None
    risk_warnings: Optional[list] = None
    timestamp: Optional[datetime] = None
    created_at: Optional[datetime] = None

@dataclass
class UserInfo:
    """用户信息表"""
    id: Optional[int] = None
    user_id: str = ""                    # 用户唯一标识
    username: str = ""                   # 用户名
    email: Optional[str] = None          # 邮箱
    phone: Optional[str] = None          # 手机号
    initial_cash: float = 1000000.0      # 初始资金，默认100万
    current_cash: float = 1000000.0      # 当前可用资金
    total_assets: float = 1000000.0      # 总资产（现金+持仓市值）
    total_profit: float = 0.0            # 总盈亏
    total_profit_ratio: float = 0.0      # 总盈亏比例
    trade_count: int = 0                 # 交易次数
    fee_rate: float = 0.0003             # 手续费率
    status: str = "active"               # 账户状态：active/inactive/frozen
    quant_stocks: Optional[Dict[str, Any]] = None  # 量化股票列表 {stock_code: {strategy, parameters}}
    quant_enabled: bool = False          # 是否开启量化交易
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class TradeFailure:
    """成交记录失败"""
    id: Optional[int] = None
    user_id: str = ""
    symbol: str = ""
    name: str = ""
    action: str = ""
    reason: str = ""
    timestamp: Optional[datetime] = None
    trade_date: Optional[datetime] = None
    signal_data: Optional[Dict[str, Any]] = None
    details: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None

@dataclass
class PositionDetail:
    """持仓明细表 - 记录每一笔买入订单的详细信息"""
    id: Optional[int] = None
    user_id: str = ""                    # 用户ID
    symbol: str = ""                     # 股票代码
    name: str = ""                       # 股票名称
    original_quantity: int = 0           # 原始买入数量（不变）
    remaining_quantity: int = 0          # 剩余持仓数量
    buy_price: float = 0.0               # 买入价格
    total_cost: float = 0.0              # 总成本
    buy_date: Optional[datetime] = None  # 买入日期
    buy_order_id: str = ""               # 原始买入订单ID
    diagnosis_data: Optional[Dict[str, Any]] = None  # 买入时的诊断信号内容
    target_price: Optional[float] = None     # 目标价
    stop_loss: Optional[float] = None        # 止损价
    support: Optional[float] = None          # 支撑位
    resistance: Optional[float] = None       # 阻力位
    sell_price: Optional[float] = None       # 止盈价/建议卖出价
    max_drawdown: Optional[float] = None     # 最大回撤阈值
    status: str = PositionStatus.ACTIVE.value  # 持仓状态
    sell_records: Optional[Dict[str, Any]] = None  # 卖出记录（部分卖出时记录）
    closed_date: Optional[datetime] = None  # 清仓日期
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# 数据库表创建SQL语句
TABLE_DEFINITIONS = {
    'stock_info': """
        CREATE TABLE IF NOT EXISTS stock_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            market TEXT NOT NULL,
            sector TEXT,
            industry TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    
    'trade_records': """
        CREATE TABLE IF NOT EXISTS trade_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            name TEXT NOT NULL,
            action TEXT NOT NULL CHECK (action IN ('buy', 'sell')),
            timestamp TIMESTAMP NOT NULL,
            trade_date DATE NOT NULL,
            price REAL NOT NULL,
            quantity INTEGER NOT NULL,
            total_cost REAL NOT NULL,
            order_id TEXT,
            signal_data TEXT, -- JSON字符串存储信号数据
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (symbol) REFERENCES stock_info (code)
        )
    """,
    
    'positions': """
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            name TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            avg_price REAL NOT NULL DEFAULT 0.0,
            total_cost REAL NOT NULL DEFAULT 0.0,
            market_value REAL NOT NULL DEFAULT 0.0,
            floating_pnl REAL NOT NULL DEFAULT 0.0,
            floating_pnl_ratio REAL NOT NULL DEFAULT 0.0,
            last_price REAL NOT NULL DEFAULT 0.0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (symbol) REFERENCES stock_info (code),
            UNIQUE(user_id, symbol)
        )
    """,
    
    'strategy_signals': """
        CREATE TABLE IF NOT EXISTS strategy_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_name TEXT NOT NULL,
            stock_code TEXT NOT NULL,
            signal_type TEXT NOT NULL CHECK (signal_type IN ('buy', 'sell', 'hold')),
            signal_strength REAL NOT NULL DEFAULT 0.0,
            signal_date TIMESTAMP NOT NULL,
            parameters TEXT, -- JSON字符串存储
            executed BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (stock_code) REFERENCES stock_info (code)
        )
    """,
    
    'market_data': """
        CREATE TABLE IF NOT EXISTS market_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            trade_date TIMESTAMP NOT NULL,
            open_price REAL NOT NULL,
            high_price REAL NOT NULL,
            low_price REAL NOT NULL,
            close_price REAL NOT NULL,
            volume INTEGER NOT NULL,
            turnover REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(stock_code, trade_date)
)
    """,
    
    'trade_notes': """
        CREATE TABLE IF NOT EXISTS trade_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            note_date TIMESTAMP NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            tags TEXT, -- 逗号分隔的标签
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (stock_code) REFERENCES stock_info (code)
        )
    """,
    
    'diagnosis_reports': """
        CREATE TABLE IF NOT EXISTS diagnosis_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            date DATE NOT NULL,
            name TEXT NOT NULL,
            current_price REAL NOT NULL,
            overall_score REAL NOT NULL,
            fundamental_score REAL NOT NULL,
            technical_score REAL NOT NULL,
            capital_score REAL NOT NULL,
            valuation_score REAL NOT NULL,
            risk_level TEXT NOT NULL CHECK (risk_level IN ('low', 'medium', 'high')),
            recommendation TEXT NOT NULL CHECK (recommendation IN ('buy', 'hold', 'sell')),
            target_price REAL,
            stop_loss REAL,
            support REAL,
            resistance REAL,
            buy_price REAL,
            sell_price REAL,
            investment_reason TEXT,
            key_indicators TEXT, -- JSON字符串存储关键指标列表
            risk_warnings TEXT, -- JSON字符串存储风险提示列表
            timestamp TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (symbol) REFERENCES stock_info (code),
            UNIQUE(symbol, date)
        )
    """,
    
    'user_info': """
        CREATE TABLE IF NOT EXISTS user_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL UNIQUE,
            username TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            initial_cash REAL NOT NULL DEFAULT 1000000.0,
            current_cash REAL NOT NULL DEFAULT 1000000.0,
            total_assets REAL NOT NULL DEFAULT 1000000.0,
            total_profit REAL NOT NULL DEFAULT 0.0,
            total_profit_ratio REAL NOT NULL DEFAULT 0.0,
            trade_count INTEGER NOT NULL DEFAULT 0,
            fee_rate REAL NOT NULL DEFAULT 0.0003,
            status TEXT NOT NULL CHECK (status IN ('active', 'inactive', 'frozen')) DEFAULT 'active',
            quant_stocks TEXT, -- JSON字符串存储量化股票列表 {stock_code: {strategy, parameters}}
            quant_enabled BOOLEAN NOT NULL DEFAULT FALSE, -- 是否开启量化交易
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    'trade_failures': """
        CREATE TABLE IF NOT EXISTS trade_failures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            name TEXT NOT NULL,
            action TEXT NOT NULL CHECK (action IN ('buy', 'sell')),
            reason TEXT NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            trade_date DATE NOT NULL,
            signal_data TEXT, -- JSON字符串存储信号数据
            details TEXT, -- JSON字符串存储失败详情
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (symbol) REFERENCES stock_info (code),
            FOREIGN KEY (user_id) REFERENCES user_info (user_id)
        )
    """,
    'position_details': """
        CREATE TABLE IF NOT EXISTS position_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            name TEXT NOT NULL,
            original_quantity INTEGER NOT NULL DEFAULT 0,
            remaining_quantity INTEGER NOT NULL DEFAULT 0,
            buy_price REAL NOT NULL DEFAULT 0.0,
            total_cost REAL NOT NULL DEFAULT 0.0,
            buy_date TIMESTAMP NOT NULL,
            buy_order_id TEXT NOT NULL,
            diagnosis_data TEXT, -- JSON字符串存储买入时的诊断信号
            target_price REAL,      -- 目标价
            stop_loss REAL,         -- 止损价
            support REAL,           -- 支撑位
            resistance REAL,        -- 阻力位
            sell_price REAL,        -- 止盈价/建议卖出价
            max_drawdown REAL,      -- 最大回撤阈值
            status TEXT NOT NULL CHECK (status IN ('active', 'partial_sold', 'closed', 'cancelled')) DEFAULT 'active',
            sell_records TEXT, -- JSON字符串存储卖出记录
            closed_date TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (symbol) REFERENCES stock_info (code),
            FOREIGN KEY (buy_order_id) REFERENCES trade_records (order_id)
        )
    """
}

# 索引定义
INDEX_DEFINITIONS = {
    'idx_trade_records_user_id': "CREATE INDEX IF NOT EXISTS idx_trade_records_user_id ON trade_records(user_id)",
    'idx_trade_records_symbol': "CREATE INDEX IF NOT EXISTS idx_trade_records_symbol ON trade_records(symbol)",
    'idx_trade_records_date': "CREATE INDEX IF NOT EXISTS idx_trade_records_date ON trade_records(trade_date)",
    'idx_trade_records_user_symbol': "CREATE INDEX IF NOT EXISTS idx_trade_records_user_symbol ON trade_records(user_id, symbol)",
    'idx_trade_records_timestamp': "CREATE INDEX IF NOT EXISTS idx_trade_records_timestamp ON trade_records(timestamp)",
    'idx_positions_user_id': "CREATE INDEX IF NOT EXISTS idx_positions_user_id ON positions(user_id)",
    'idx_positions_symbol': "CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol)",
    'idx_positions_user_symbol': "CREATE INDEX IF NOT EXISTS idx_positions_user_symbol ON positions(user_id, symbol)",
    'idx_strategy_signals_stock_code': "CREATE INDEX IF NOT EXISTS idx_strategy_signals_stock_code ON strategy_signals(stock_code)",
    'idx_strategy_signals_date': "CREATE INDEX IF NOT EXISTS idx_strategy_signals_date ON strategy_signals(signal_date)",
    'idx_market_data_stock_date': "CREATE INDEX IF NOT EXISTS idx_market_data_stock_date ON market_data(stock_code, trade_date)",
    'idx_trade_notes_stock_code': "CREATE INDEX IF NOT EXISTS idx_trade_notes_stock_code ON trade_notes(stock_code)",
    'idx_diagnosis_reports_symbol': "CREATE INDEX IF NOT EXISTS idx_diagnosis_reports_symbol ON diagnosis_reports(symbol)",
    'idx_diagnosis_reports_date': "CREATE INDEX IF NOT EXISTS idx_diagnosis_reports_date ON diagnosis_reports(date)",
    'idx_diagnosis_reports_symbol_date': "CREATE INDEX IF NOT EXISTS idx_diagnosis_reports_symbol_date ON diagnosis_reports(symbol, date)",
    'idx_diagnosis_reports_recommendation': "CREATE INDEX IF NOT EXISTS idx_diagnosis_reports_recommendation ON diagnosis_reports(recommendation)",
    'idx_diagnosis_reports_risk_level': "CREATE INDEX IF NOT EXISTS idx_diagnosis_reports_risk_level ON diagnosis_reports(risk_level)",
    'idx_trade_failures_user_id': "CREATE INDEX IF NOT EXISTS idx_trade_failures_user_id ON trade_failures(user_id)",
    'idx_trade_failures_symbol': "CREATE INDEX IF NOT EXISTS idx_trade_failures_symbol ON trade_failures(symbol)",
    'idx_trade_failures_date': "CREATE INDEX IF NOT EXISTS idx_trade_failures_date ON trade_failures(trade_date)",
    'idx_trade_failures_user_symbol': "CREATE INDEX IF NOT EXISTS idx_trade_failures_user_symbol ON trade_failures(user_id, symbol)",
    'idx_user_info_user_id': "CREATE INDEX IF NOT EXISTS idx_user_info_user_id ON user_info(user_id)",
    'idx_user_info_username': "CREATE INDEX IF NOT EXISTS idx_user_info_username ON user_info(username)",
    'idx_user_info_status': "CREATE INDEX IF NOT EXISTS idx_user_info_status ON user_info(status)",
    'idx_user_info_quant_enabled': "CREATE INDEX IF NOT EXISTS idx_user_info_quant_enabled ON user_info(quant_enabled)",
    'idx_trade_failures_reason': "CREATE INDEX IF NOT EXISTS idx_trade_failures_reason ON trade_failures(reason)",
    'idx_position_details_user_id': "CREATE INDEX IF NOT EXISTS idx_position_details_user_id ON position_details(user_id)",
    'idx_position_details_symbol': "CREATE INDEX IF NOT EXISTS idx_position_details_symbol ON position_details(symbol)",
    'idx_position_details_user_symbol': "CREATE INDEX IF NOT EXISTS idx_position_details_user_symbol ON position_details(user_id, symbol)",
    'idx_position_details_status': "CREATE INDEX IF NOT EXISTS idx_position_details_status ON position_details(status)",
    'idx_position_details_buy_order_id': "CREATE INDEX IF NOT EXISTS idx_position_details_buy_order_id ON position_details(buy_order_id)",
    'idx_position_details_buy_date': "CREATE INDEX IF NOT EXISTS idx_position_details_buy_date ON position_details(buy_date)",
    'idx_position_details_closed_date': "CREATE INDEX IF NOT EXISTS idx_position_details_closed_date ON position_details(closed_date)"
}

# SQLite数据库使用指南

本文档介绍如何在项目中使用SQLite数据库功能。

## 功能概述

我们提供了完整的SQLite数据库支持，包括：

- **数据库连接管理**: 自动管理数据库连接和连接池
- **数据模型定义**: 预定义的交易相关数据模型
- **数据存储服务**: 提供数据的插入、更新、删除功能
- **数据查询服务**: 提供丰富的查询和统计功能

## 文件结构

```
backend/service/
├── __init__.py           # 模块导出
├── database_manager.py   # 数据库连接管理
├── models.py            # 数据模型定义
├── data_service.py      # 数据存储服务
├── query_service.py     # 数据查询服务
```

## 快速开始

### 1. 导入服务

```python
from backend.service import data_service, query_service
from backend.service.models import StockInfo, TradeRecord, Position
```

### 2. 基本使用示例

#### 保存股票信息
```python
stock = StockInfo(
    code="00700",
    name="腾讯控股",
    market="HK",
    sector="科技",
    industry="互联网"
)
data_service.save_stock_info(stock)
```

#### 保存交易记录
```python
trade = TradeRecord(
    stock_code="00700",
    stock_name="腾讯控股",
    trade_date=datetime.now(),
    direction="buy",
    price=400.0,
    volume=100,
    amount=40000.0,
    commission=100.0,
    status="executed"
)
data_service.save_trade_record(trade)
```

#### 查询股票信息
```python
# 获取单只股票信息
stock_info = query_service.get_stock_info("00700")

# 搜索股票
search_results = query_service.search_stocks("腾讯")

# 获取所有股票
all_stocks = query_service.get_all_stocks()
```

#### 查询交易记录
```python
# 获取特定股票的交易记录
trades = query_service.get_trade_records(stock_code="00700")

# 获取交易汇总
summary = query_service.get_trade_summary("00700")
```

#### 查询持仓信息
```python
# 获取所有持仓
positions = query_service.get_positions()

# 获取持仓汇总
summary = query_service.get_position_summary()
```

## 数据模型

### StockInfo - 股票基本信息
- `code`: 股票代码
- `name`: 股票名称
- `market`: 市场代码 (HK, SH, SZ, US)
- `sector`: 行业板块
- `industry`: 细分行业

### TradeRecord - 交易记录
- `stock_code`: 股票代码
- `stock_name`: 股票名称
- `trade_date`: 交易日期
- `direction`: 交易方向 (buy/sell)
- `price`: 成交价格
- `volume`: 成交数量
- `amount`: 成交金额
- `commission`: 佣金
- `status`: 订单状态

### Position - 持仓信息
- `stock_code`: 股票代码
- `stock_name`: 股票名称
- `current_volume`: 当前持仓数量
- `average_price`: 平均持仓成本
- `market_value`: 市值
- `cost_value`: 成本金额
- `floating_pnl`: 浮动盈亏
- `floating_pnl_ratio`: 浮动盈亏比例

### StrategySignal - 策略信号
- `strategy_name`: 策略名称
- `stock_code`: 股票代码
- `signal_type`: 信号类型 (buy/sell/hold)
- `signal_strength`: 信号强度
- `signal_date`: 信号日期
- `parameters`: 策略参数
- `executed`: 是否已执行

### MarketData - 市场数据
- `stock_code`: 股票代码
- `trade_date`: 交易日期
- `open_price`: 开盘价
- `high_price`: 最高价
- `low_price`: 最低价
- `close_price`: 收盘价
- `volume`: 成交量
- `turnover`: 成交额

## 高级查询功能

### 交易记录查询
```python
# 按条件查询
trades = query_service.get_trade_records(
    stock_code="00700",
    start_date=datetime.now() - timedelta(days=30),
    end_date=datetime.now(),
    direction="buy"
)
```

### 策略信号查询
```python
# 获取未执行的信号
unexecuted_signals = query_service.get_unexecuted_signals()

# 按策略查询
signals = query_service.get_strategy_signals(
    strategy_name="均线策略",
    stock_code="00700"
)
```

### 统计查询
```python
# 每日盈亏统计
daily_pnl = query_service.get_daily_pnl()

# 股票表现统计
performance = query_service.get_stock_performance("00700", days=30)
```

## 批量操作

### 批量保存股票信息
```python
stocks = [
    StockInfo(code="00700", name="腾讯控股", market="HK"),
    StockInfo(code="AAPL", name="苹果公司", market="US"),
    StockInfo(code="MSFT", name="微软", market="US")
]
data_service.batch_save_stock_info(stocks)
```

### 批量保存市场数据
```python
market_data_list = [
    MarketData(stock_code="00700", trade_date=date1, ...),
    MarketData(stock_code="00700", trade_date=date2, ...),
    # ...
]
data_service.batch_save_market_data(market_data_list)
```

## 数据库文件位置

数据库文件默认存储在：
```
data/database/quant_trading.db
```

## 运行测试

执行测试脚本来验证所有功能：

```bash
python test_database_usage.py
```

## 注意事项

1. **线程安全**: 数据库连接管理器是线程安全的，可以在多线程环境中使用
2. **自动初始化**: 首次使用时会自动创建数据库表和索引
3. **数据完整性**: 使用外键约束确保数据完整性
4. **性能优化**: 已创建必要的索引以提高查询性能

## 扩展开发

### 添加新表

1. 在 `models.py` 中添加表定义SQL
2. 在 `data_service.py` 中添加对应的保存方法
3. 在 `query_service.py` 中添加对应的查询方法

### 自定义查询

可以直接使用 `db_manager` 执行自定义SQL：

```python
from backend.service import db_manager

# 执行自定义查询
results = db_manager.execute_query("SELECT * FROM trade_records WHERE amount > ?", (10000,))

# 执行自定义更新
affected = db_manager.execute_update("UPDATE positions SET last_price = ? WHERE stock_code = ?", (price, code))

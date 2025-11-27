# 量化交易模块使用指南

## 📋 功能概述

基于一键诊断功能的智能量化交易模块，支持单股票和多股票的自动化交易决策。

## 🚀 快速开始

### 1. 集成到FastAPI应用

在 `app.py` 中添加以下代码：

```python
from quant_trading_api import router as quant_trading_router

# 注册量化交易路由
app.include_router(quant_trading_router)
```

### 2. 基本使用示例

#### 单股票交易决策

```python
from service.quant_trading import process_trading_decision

# 模拟诊断结果
diagnosis_result = {
    'overall_score': 85.5,
    'technical_score': 80.0,
    'capital_score': 75.0,
    # 其他诊断数据...
}

# 获取交易信号
result = process_trading_decision('000001.SZ', diagnosis_result)
print(f"交易信号: {result['signal']}")
print(f"建议仓位: {result['position_size']*100}%")
print(f"止损价格: {result['stop_loss']}")
```

#### 批量股票处理

```python
from service.quant_trading import process_trading_decisions

stock_list = [
    {
        'symbol': '000001.SZ',
        'diagnosis_result': {'overall_score': 85.5, 'technical_score': 80.0, 'capital_score': 75.0}
    },
    {
        'symbol': '600519.SH',
        'diagnosis_result': {'overall_score': 45.2, 'technical_score': 40.0, 'capital_score': 35.0}
    }
]

results = process_trading_decisions(stock_list)
for result in results:
    print(f"{result['symbol']}: {result['signal']} - 置信度: {result['confidence']:.2f}")
```

## 📡 API接口

### 1. 单股票交易决策

**POST** `/api/quant/decision/single`

**请求体:**
```json
{
  "symbol": "000001.SZ",
  "diagnosis_result": {
    "overall_score": 85.5,
    "technical_score": 80.0,
    "capital_score": 75.0
  }
}
```

**响应:**
```json
{
  "success": true,
  "data": {
    "symbol": "000001.SZ",
    "signal": "strong_buy",
    "confidence": 0.86,
    "reason": "综合评分优秀(85.5分)，技术面和资金面均表现良好",
    "price": 10.0,
    "position_size": 0.08,
    "stop_loss": 9.2,
    "take_profit": 11.5,
    "risk_level": "low",
    "timestamp": "2024-10-24T18:30:00"
  }
}
```

### 2. 批量交易决策

**POST** `/api/quant/decision/batch`

**请求体:**
```json
{
  "stocks": [
    {
      "symbol": "000001.SZ",
      "diagnosis_result": {"overall_score": 85.5, "technical_score": 80.0, "capital_score": 75.0}
    },
    {
      "symbol": "600519.SH",
      "diagnosis_result": {"overall_score": 45.2, "technical_score": 40.0, "capital_score": 35.0}
    }
  ]
}
```

### 3. 执行交易

**POST** `/api/quant/execute`

**请求体:**
```json
{
  "symbol": "000001.SZ",
  "action": "buy",
  "quantity": 1000,
  "price": 10.5
}
```

### 4. 获取投资组合

**GET** `/api/quant/portfolio`

**响应:**
```json
{
  "success": true,
  "data": {
    "initial_capital": 1000000.0,
    "current_capital": 850000.0,
    "total_value": 920000.0,
    "total_pnl": -80000.0,
    "total_return": -8.0,
    "positions": {"000001.SZ": 10000, "600519.SH": 500},
    "position_count": 2,
    "trade_count": 15
  }
}
```

### 5. 获取交易信号历史

**GET** `/api/quant/signals?symbol=000001.SZ&limit=10`

## 🎯 信号生成逻辑

### 评分体系

| 维度 | 权重 | 评分标准 |
|---|---|---|
| 综合评分 | 100% | 基于一键诊断结果 |
| 技术评分 | 参考 | EMA趋势、价格关系 |
| 资金评分 | 参考 | 主力流向、资金实力 |

### 信号类型

- **strong_buy**: 综合评分≥80，强烈建议买入
- **buy**: 综合评分≥70，建议买入
- **hold**: 综合评分40-70，建议观望
- **sell**: 综合评分≤40，建议卖出
- **strong_sell**: 综合评分≤30，强烈建议卖出

### 仓位管理

- **strong_buy**: 8% 仓位
- **buy**: 5% 仓位
- **其他**: 0% 仓位

### 风险控制

- **最大持仓股票数**: 20只
- **单只股票最大仓位**: 10%
- **日最大亏损**: 2%
- **止损比例**: 8%
- **止盈比例**: 15%

## 🔧 配置参数

### 更新交易配置

**POST** `/api/quant/config`

**请求体:**
```json
{
  "max_position_size": 0.15,
  "max_daily_loss": 0.03,
  "min_confidence": 0.7,
  "stop_loss_pct": 0.1,
  "take_profit_pct": 0.2,
  "max_stocks": 15
}
```

## 📊 使用场景

### 1. 实时监控
```python
# 每5分钟检查一次持仓股票
for symbol in watchlist:
    diagnosis = get_diagnosis(symbol)
    signal = process_trading_decision(symbol, diagnosis)
    if signal['signal'] in ['sell', 'strong_sell']:
        send_alert(symbol, signal)
```

### 2. 批量选股
```python
# 每日收盘后批量分析
all_stocks = get_all_stocks()
diagnosis_results = batch_diagnose(all_stocks)
trading_signals = process_trading_decisions(diagnosis_results)

# 选出前10名买入信号
buy_signals = [s for s in trading_signals if s['signal'] in ['buy', 'strong_buy']]
top_buy_signals = sorted(buy_signals, key=lambda x: x['confidence'], reverse=True)[:10]
```

### 3. 回测系统
```python
# 历史数据回测
engine = QuantTradingEngine(initial_capital=1000000)

for date, data in historical_data.items():
    for symbol, diagnosis in data.items():
        signal = engine.diagnose_stock(symbol, diagnosis)
        if signal.signal_type != SignalType.HOLD:
            engine.execute_trade(symbol, signal.signal_type.value, 
                               signal.quantity, signal.price)
```

## 🚨 注意事项

1. **数据依赖**: 需要实时行情数据和诊断结果
2. **风险控制**: 建议设置合理的止损止盈
3. **资金管理**: 不要满仓操作，保留部分现金
4. **回测验证**: 实盘前建议进行历史回测
5. **监控频率**: 根据策略调整监控频率

## 🔍 调试和日志

### 查看日志
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# 查看详细交易日志
signals = trading_engine.get_trading_signals(limit=100)
for signal in signals:
    print(f"{signal['timestamp']} - {signal['symbol']}: {signal['signal']}")
```

### 错误处理

所有API接口都包含错误处理，返回格式：
```json
{
  "success": false,
  "error": "错误描述"
}

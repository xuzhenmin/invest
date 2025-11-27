# 日志配置使用说明

## 📋 概述

本项目使用配置文件管理日志系统，支持多种日志级别、格式和输出方式。

## 🛠️ 配置文件

### 1. 配置文件位置
- `backend/logging.yaml` - YAML格式配置文件（推荐）
- `backend/logging.conf` - INI格式配置文件

### 2. 环境变量
- `LOG_CFG` - 指定日志配置文件路径
- 示例：`export LOG_CFG=/path/to/logging.yaml`

## 📁 日志文件结构

```
backend/
├── logs/
│   ├── app.log          # 应用日志（INFO级别及以上）
│   ├── error.log        # 错误日志（ERROR级别及以上）
│   ├── debug.log        # 调试日志（所有级别）
│   └── .gitkeep        # 保持目录结构
├── logging.yaml         # YAML格式配置
├── logging.conf         # INI格式配置
└── utils/
    └── logger_config.py # 日志配置工具
```

## 🚀 使用方法

### 1. 基本使用
```python
from utils.logger_config import setup_logging, get_logger

# 初始化日志配置
setup_logging()

# 获取logger
logger = get_logger('app')
logger.info("应用启动成功")
```

### 2. 使用自定义配置文件
```python
from utils.logger_config import setup_logging

# 使用YAML配置文件
setup_logging('logging.yaml')

# 使用INI配置文件
setup_logging('logging.conf')

# 使用环境变量指定的配置文件
setup_logging()  # 自动读取LOG_CFG环境变量
```

### 3. 动态调整日志级别
```python
from utils.logger_config import set_log_level
import logging

# 设置特定模块的日志级别
set_log_level('service', logging.DEBUG)
set_log_level('storage', logging.WARNING)
```

## 📊 日志级别

| 级别 | 数值 | 用途 |
|------|------|------|
| DEBUG | 10 | 调试信息 |
| INFO | 20 | 一般信息 |
| WARNING | 30 | 警告信息 |
| ERROR | 40 | 错误信息 |
| CRITICAL | 50 | 严重错误 |

## 🔧 配置说明

### 1. 日志轮转
- **app.log**: 按文件大小轮转（10MB，保留5个备份）
- **error.log**: 按文件大小轮转（10MB，保留5个备份）
- **debug.log**: 按时间轮转（每天午夜，保留30天）

### 2. 日志格式
- **detailed**: 包含时间、模块、级别、文件名、行号等详细信息
- **simple**: 简洁格式，适合控制台输出
- **json**: JSON格式，适合日志分析系统

### 3. 模块分类
- **app**: 主应用日志
- **service**: 服务层日志
- **storage**: 存储层日志
- **quant**: 量化模块日志
- **uvicorn**: Web服务器日志

## 🧪 测试日志配置

运行测试脚本验证配置：
```bash
cd backend
python3 test_logging.py
```

## 📝 最佳实践

### 1. 模块内使用
```python
# 在每个模块顶部
from utils.logger_config import get_logger
logger = get_logger(__name__)

# 使用logger
logger.info("模块初始化完成")
logger.error("发生错误", exc_info=True)
```

### 2. 异常处理
```python
try:
    # 业务逻辑
    result = risky_operation()
except Exception as e:
    logger.exception(f"操作失败: {e}")
    # 或者
    logger.error(f"操作失败: {e}", exc_info=True)
```

### 3. 性能敏感代码
```python
if logger.isEnabledFor(logging.DEBUG):
    logger.debug(f"复杂计算结果: {expensive_operation()}")
```

## 🔍 故障排除

### 1. 日志文件未生成
- 检查`logs/`目录权限
- 确认配置文件格式正确
- 检查磁盘空间

### 2. 日志级别不生效
- 确认配置文件中的级别设置
- 检查是否有环境变量覆盖
- 验证logger名称是否正确

### 3. 日志重复输出
- 检查`propagate`设置
- 确认handler配置是否正确

## 🔄 迁移指南

从旧配置迁移到新配置：

1. 替换原有的`logging.basicConfig()`调用
2. 使用`get_logger(__name__)`替代`logging.getLogger(__name__)`
3. 确保所有模块都使用统一的日志配置

## 📈 监控建议

- 定期检查日志文件大小
- 设置日志文件清理策略
- 监控错误日志频率
- 使用日志分析工具进行性能分析

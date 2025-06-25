# 量化交易系统后端

这是一个基于FastAPI的量化交易系统后端，集成了Deepseek API进行市场分析。

## 环境要求

- Python 3.8+
- pip

## 安装

1. 创建虚拟环境（推荐）：
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
.\venv\Scripts\activate  # Windows
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 配置环境变量：
创建 `.env` 文件并添加以下配置：
```
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_API_URL=https://api.deepseek.com/v1
```

## 运行

```bash
uvicorn app.main:app --reload
```

服务器将在 http://localhost:8000 运行

## API文档

启动服务器后，访问 http://localhost:8000/docs 查看完整的API文档。

## 主要功能

- 市场分析
- 股票列表获取
- Deepseek API集成

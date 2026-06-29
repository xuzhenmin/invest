"""
数据管道统一入口

对外暴露三个惰性初始化的单例：
  - macro_store      : MacroDataStore，宏观数据查询（PMI/CPI/利率/大宗等）
  - miaoxiang        : MiaoXiangClient，东方财富妙想智能选股 / 资讯搜索
  - financial_client : FinancialDataClient，蚂蚁金融专业数据 API

两个 API 客户端在 Key 未配置时返回 None，不影响服务启动。
"""

import os
from dotenv import load_dotenv

# 确保 .env 已加载（app.py 启动前可能还没 load）
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
load_dotenv(dotenv_path=_env_path, override=False)

try:
    from utils.logger_config import get_logger
    logger = get_logger('datapip')
except Exception:
    import logging
    logger = logging.getLogger('datapip')

# ──────────────────────────────────────────────
# 1. 宏观数据 Store（依赖 db_manager，始终可用）
# ──────────────────────────────────────────────
_macro_store = None

def _get_macro_store():
    global _macro_store
    if _macro_store is None:
        try:
            from service.datapip.spilder.macro_storage import MacroDataStore
            _macro_store = MacroDataStore()
            logger.info("[datapip] MacroDataStore 初始化成功")
        except Exception as e:
            logger.error(f"[datapip] MacroDataStore 初始化失败: {e}")
    return _macro_store

class _MacroStoreProxy:
    """代理对象，首次调用时才真正初始化 MacroDataStore。"""
    def __getattr__(self, name):
        store = _get_macro_store()
        if store is None:
            raise RuntimeError("MacroDataStore 不可用，请检查日志")
        return getattr(store, name)

macro_store = _MacroStoreProxy()

# ──────────────────────────────────────────────
# 2. 妙想客户端
# ──────────────────────────────────────────────
_miaoxiang = None
_miaoxiang_initialized = False

def _get_miaoxiang():
    global _miaoxiang, _miaoxiang_initialized
    if not _miaoxiang_initialized:
        _miaoxiang_initialized = True
        api_key = os.getenv('MX_APIKEY')
        if not api_key:
            logger.warning("[datapip] MX_APIKEY 未配置，MiaoXiangClient 不可用")
        else:
            try:
                from service.datapip.miaoxiang_client import MiaoXiangClient
                _miaoxiang = MiaoXiangClient(api_key=api_key)
                logger.info("[datapip] MiaoXiangClient 初始化成功")
            except Exception as e:
                logger.error(f"[datapip] MiaoXiangClient 初始化失败: {e}")
    return _miaoxiang

class _MiaoXiangProxy:
    """代理对象，首次调用时才真正初始化 MiaoXiangClient。"""
    def __getattr__(self, name):
        client = _get_miaoxiang()
        if client is None:
            raise RuntimeError("MiaoXiangClient 不可用，请检查 MX_APIKEY 配置")
        return getattr(client, name)

    def is_available(self) -> bool:
        return _get_miaoxiang() is not None

miaoxiang = _MiaoXiangProxy()

# ──────────────────────────────────────────────
# 3. 金融数据专业 API 客户端
# ──────────────────────────────────────────────
_financial_client = None
_financial_initialized = False

def _get_financial_client():
    global _financial_client, _financial_initialized
    if not _financial_initialized:
        _financial_initialized = True
        api_key = os.getenv('FINANCIAL_DATA_API_KEY')
        if not api_key:
            logger.warning("[datapip] FINANCIAL_DATA_API_KEY 未配置，FinancialDataClient 不可用")
        else:
            try:
                from service.datapip.financial_data_client import FinancialDataClient
                _financial_client = FinancialDataClient(api_key=api_key)
                logger.info("[datapip] FinancialDataClient 初始化成功")
            except Exception as e:
                logger.error(f"[datapip] FinancialDataClient 初始化失败: {e}")
    return _financial_client

class _FinancialClientProxy:
    """代理对象，首次调用时才真正初始化 FinancialDataClient。"""
    def __getattr__(self, name):
        client = _get_financial_client()
        if client is None:
            raise RuntimeError("FinancialDataClient 不可用，请检查 FINANCIAL_DATA_API_KEY 配置")
        return getattr(client, name)

    def is_available(self) -> bool:
        return _get_financial_client() is not None

financial_client = _FinancialClientProxy()

__all__ = ['macro_store', 'miaoxiang', 'financial_client']

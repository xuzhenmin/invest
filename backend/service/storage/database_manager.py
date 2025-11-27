"""
SQLite数据库连接管理模块
提供数据库连接池和基础操作封装
"""

import sqlite3
import os
import threading
from contextlib import contextmanager
from typing import Optional, Dict, Any, List, Tuple
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    """SQLite数据库管理器"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.db_path = None
            self.connection_pool = {}
            self.initialized = True
    
    def initialize(self, db_path: str = None):
        """初始化数据库连接
        
        Args:
            db_path: 数据库文件路径，如果为None则使用默认路径
        """
        if db_path is None:
            # 使用项目根目录下的data文件夹
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            db_dir = os.path.join(project_root, 'data', 'database')
            os.makedirs(db_dir, exist_ok=True)
            self.db_path = os.path.join(db_dir, 'quant_trading.db')
        else:
            self.db_path = db_path
            
        # 确保数据库文件目录存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        logger.info(f"数据库初始化完成: {self.db_path}")
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接的上下文管理器"""
        if self.db_path is None:
            self.initialize()
            
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # 使查询结果可以通过列名访问
        
        try:
            yield conn
        finally:
            conn.close()
    
    def execute_query(self, query: str, params: Tuple = None) -> List[Dict[str, Any]]:
        """执行查询语句
        
        Args:
            query: SQL查询语句
            params: 查询参数
            
        Returns:
            查询结果列表
        """
        # 打印SQL和参数用于调试
        logger.info(f"[SQL_QUERY] {query}")
        if params:
            logger.info(f"[SQL_PARAMS] {params}")
            
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            rows = cursor.fetchall()
            logger.info(f"[SQL_RESULT] 返回 {len(rows)} 条记录")
            return [dict(row) for row in rows]
    
    def execute_update(self, query: str, params: Tuple = None) -> int:
        """执行更新/插入/删除语句
        
        Args:
            query: SQL语句
            params: 参数
            
        Returns:
            影响的行数
        """
        # 打印SQL和参数用于调试
        logger.info(f"[SQL_UPDATE] {query}")
        # if params:
        #     logger.info(f"[SQL_PARAMS] {params}")
            
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            conn.commit()
            affected_rows = cursor.lastrowid if cursor.lastrowid else cursor.rowcount
            logger.info(f"[SQL_AFFECTED] 影响 {affected_rows} 行")
            return affected_rows
    
    def execute_many(self, query: str, params_list: List[Tuple]) -> int:
        """批量执行SQL语句
        
        Args:
            query: SQL语句
            params_list: 参数列表
            
        Returns:
            影响的行数
        """
        # 打印SQL和参数用于调试
        logger.info(f"[SQL_BATCH] {query}")
        logger.info(f"[SQL_BATCH_PARAMS] 批量执行 {len(params_list)} 组参数")
        if params_list and len(params_list) <= 5:  # 只打印前5组参数避免日志过多
            logger.info(f"[SQL_BATCH_PARAMS_SAMPLE] {params_list[:5]}")
            
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            conn.commit()
            affected_rows = cursor.rowcount
            logger.info(f"[SQL_BATCH_AFFECTED] 批量执行影响 {affected_rows} 行")
            return affected_rows
    
    def table_exists(self, table_name: str) -> bool:
        """检查表是否存在
        
        Args:
            table_name: 表名
            
        Returns:
            表是否存在
        """
        query = """
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name=?
        """
        result = self.execute_query(query, (table_name,))
        return len(result) > 0
    
    def create_table(self, create_sql: str):
        """创建表
        
        Args:
            create_sql: 创建表的SQL语句
        """
        self.execute_update(create_sql)
        logger.info("表创建成功")

# 全局数据库管理器实例
db_manager = DatabaseManager()

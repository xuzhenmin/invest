"""
日志配置工具模块
提供统一的日志配置和管理功能
"""

import os
import logging
import logging.config
import yaml
from typing import Optional

def setup_logging(
    config_path: Optional[str] = None,
    default_level: int = logging.INFO,
    env_key: str = 'LOG_CFG'
) -> None:
    """
    设置日志配置
    
    Args:
        config_path: 配置文件路径，如果为None则使用默认配置
        default_level: 默认日志级别
        env_key: 环境变量key，用于指定配置文件路径
    """
    # 创建日志目录
    log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # 从环境变量获取配置文件路径
    config_path = config_path or os.getenv(env_key)
    
    if config_path and os.path.exists(config_path):
        # 使用配置文件
        if config_path.endswith('.yaml') or config_path.endswith('.yml'):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logging.config.dictConfig(config)
        elif config_path.endswith('.conf'):
            logging.config.fileConfig(config_path, disable_existing_loggers=False)
        else:
            logging.basicConfig(level=default_level)
    else:
        # 使用默认配置
        _setup_default_logging(log_dir, default_level)

def _setup_default_logging(log_dir: str, level: int) -> None:
    """设置默认日志配置"""
    
    # 确保日志目录存在
    os.makedirs(log_dir, exist_ok=True)
    
    # 默认配置
    default_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'detailed': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
            'simple': {
                'format': '%(asctime)s - %(levelname)s - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': 'INFO',
                'formatter': 'simple',
                'stream': 'ext://sys.stdout'
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': 'INFO',
                'formatter': 'detailed',
                'filename': os.path.join(log_dir, 'app.log'),
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
                'encoding': 'utf8'
            },
            'error_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': 'ERROR',
                'formatter': 'detailed',
                'filename': os.path.join(log_dir, 'error.log'),
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
                'encoding': 'utf8'
            },
            'debug_file': {
                'class': 'logging.handlers.TimedRotatingFileHandler',
                'level': 'DEBUG',
                'formatter': 'detailed',
                'filename': os.path.join(log_dir, 'debug.log'),
                'when': 'midnight',
                'interval': 1,
                'backupCount': 30,
                'encoding': 'utf8'
            }
        },
        'loggers': {
            'app': {
                'level': 'DEBUG',
                'handlers': ['console', 'file', 'error_file', 'debug_file'],
                'propagate': False
            },
            'service': {
                'level': 'DEBUG',
                'handlers': ['file', 'error_file', 'debug_file'],
                'propagate': False
            },
            'storage': {
                'level': 'DEBUG',
                'handlers': ['file', 'error_file', 'debug_file'],
                'propagate': False
            },
            'quant': {
                'level': 'DEBUG',
                'handlers': ['file', 'error_file', 'debug_file'],
                'propagate': False
            }
        },
        'root': {
            'level': 'INFO',
            'handlers': ['console', 'file', 'error_file']
        }
    }
    
    logging.config.dictConfig(default_config)

def get_logger(name: str) -> logging.Logger:
    """
    获取指定名称的logger
    
    Args:
        name: logger名称
    
    Returns:
        logging.Logger实例
    """
    return logging.getLogger(name)

def set_log_level(logger_name: str, level: int) -> None:
    """
    设置指定logger的日志级别
    
    Args:
        logger_name: logger名称
        level: 日志级别 (logging.DEBUG, logging.INFO, etc.)
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

def add_file_handler(logger_name: str, filename: str, level: int = logging.INFO) -> None:
    """
    为指定logger添加文件处理器
    
    Args:
        logger_name: logger名称
        filename: 日志文件路径
        level: 日志级别
    """
    logger = logging.getLogger(logger_name)
    handler = logging.handlers.RotatingFileHandler(
        filename,
        maxBytes=10485760,
        backupCount=5,
        encoding='utf8'
    )
    handler.setLevel(level)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

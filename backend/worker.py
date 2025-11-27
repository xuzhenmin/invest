import os
import sys
import time
import threading
import logging
import requests
import json
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 后端API地址
API_BASE_URL = os.environ.get('API_BASE_URL', 'http://localhost:5001')

# 用户监控配置文件路径（与app.py一致）
monitor_config_file = os.path.join(os.path.dirname(__file__), 'user_monitor_config.json')

# 频率到秒的映射
def freq_to_seconds(freq):
    if freq == '5min':
        return 5 * 60
    elif freq == '30min':
        return 30 * 60
    elif freq == '1d':
        return 24 * 60 * 60
    else:
        return 5 * 60  # 默认5分钟

# 读取所有用户配置
def load_monitor_config():
    if not os.path.exists(monitor_config_file):
        return {}
    with open(monitor_config_file, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except Exception:
            return {}

# 执行单个用户的所有规则
def execute_user_rules(user_id, conf):
    rules = conf.get('rules', [])
    if not rules:
        logger.info(f"用户{user_id}未设置任何规则，跳过")
        return
    for rule in rules:
        try:
            logger.info(f"开始执行 用户{user_id} 规则[{rule}] ...")
            payload = {'userId': user_id}
            url = f"{API_BASE_URL}/watchlist/{rule}/execute"
            resp = requests.post(url, json=payload, timeout=60)
            if resp.status_code == 200:
                logger.info(f"用户{user_id} 规则[{rule}] 执行成功: {resp.text}")
            else:
                logger.warning(f"用户{user_id} 规则[{rule}] 执行失败: {resp.status_code} {resp.text}")
            logger.info(f"结束执行 用户{user_id} 规则[{rule}]")
        except Exception as e:
            logger.error(f"用户{user_id} 规则[{rule}] 执行异常: {e}")

# 主调度循环
def scheduler():
    logger.info("调度循环启动")
    last_run = {}  # user_id -> 上次执行时间戳
    # 启动时将所有用户的last_run初始化为当前时间，避免立即执行
    all_conf = load_monitor_config()
    now = time.time()
    for user_id in all_conf.keys():
        last_run[user_id] = now
    while True:
        all_conf = load_monitor_config()
        now = time.time()
        for user_id, conf in all_conf.items():
            freq = conf.get('frequency', '5min')
            interval = freq_to_seconds(freq)
            last = last_run.get(user_id, now)
            if now - last >= interval:
                logger.info(f"调度执行用户{user_id}，频率{freq}")
                execute_user_rules(user_id, conf)
                last_run[user_id] = now
        logger.info("调度循环结束，sleep 30s ...")
        time.sleep(30)  # 每30秒检查一次

if __name__ == '__main__':
    logger.info("启动监控调度worker...")
    scheduler() 

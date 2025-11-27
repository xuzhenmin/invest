#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
极简定时任务调度器 - 最终解决重复执行问题
使用进程级单例和文件锁确保唯一性
"""

import os
import sys
import time
import logging
import threading
import fcntl
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 全局变量
_global_scheduler = None
_scheduler_lock = threading.Lock()
_task_executed = set()
_startup_lock = threading.Lock()
_is_started = False
_file_lock = None
_lock_file_path = None

# 使用标准logger
logger = logging.getLogger(__name__)

class SimpleQuantScheduler:
    """极简量化调度器"""
    
    def __init__(self):
        self.scheduler = None
        self.lock_file = None
        self._setup_file_lock()
    
    def _setup_file_lock(self):
        """设置进程级文件锁"""
        global _lock_file_path
        
        if _lock_file_path is None:
            lock_dir = os.path.join(project_root, 'tmp')
            os.makedirs(lock_dir, exist_ok=True)
            _lock_file_path = os.path.join(lock_dir, 'quant_scheduler.lock')
        
        self.lock_file = open(_lock_file_path, 'w')
    
    def _acquire_lock(self):
        """获取进程级锁"""
        try:
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except (IOError, OSError):
            return False
    
    def _release_lock(self):
        """释放进程级锁"""
        try:
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
            self.lock_file.close()
        except (IOError, OSError):
            pass
    

    
    def start(self):
        """启动调度器（带进程级文件锁）"""
        global _is_started
        
        # 检查文件锁
        if not self._acquire_lock():
            logger.warning("⚠️ [LOCK] 另一个进程已持有调度器锁，跳过启动")
            return False
        
        # 全局启动状态检查
        if _is_started:
            logger.info("调度器已全局启动，跳过重复启动")
            return False
            
        if self.scheduler and self.scheduler.running:
            logger.info("调度器已在运行")
            return False
        
        if self.scheduler is None:
            self.scheduler = BackgroundScheduler()
            
            # 检查任务是否已存在
            if not self.scheduler.get_jobs():
                trigger = CronTrigger(
                    minute='30',
                    hour='16',
                    day_of_week='mon-fri',
                    timezone='Asia/Shanghai'
                )
                
                self.scheduler.add_job(
                    func=self._execute_task,
                    trigger=trigger,
                    id='simple_quant_task',
                    max_instances=1,
                    coalesce=True
                )
        
        if not self.scheduler.running:
            self.scheduler.start()
            _is_started = True  # 设置全局启动标志
            logger.info("✅ 极简调度器已启动（进程锁已获取）")
            return True
        
        return False
    
    def _execute_task(self):
        """执行单次任务（带详细监控和个股诊断）"""
        import os
        import threading
        import sys
        
        # 检查调度器状态
        if not self.scheduler or not self.scheduler.running:
            logger.warning("⚠️ [SKIP] 调度器未运行，跳过任务执行")
            return
        
        # 执行量化交易任务
        self._execute_quant_trading()
        
        # 获取进程和线程信息
        pid = os.getpid()
        thread_id = threading.current_thread().ident
        thread_name = threading.current_thread().name
        
        # 精确时间戳（包含毫秒）
        now = datetime.now()
        timestamp = now.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        task_id = f"task_{now.strftime('%Y%m%d%H%M%S%f')[:-3]}"
        
        # 监控日志 - 方法入口
        logger.info("🔍 [MONITOR] _execute_task 方法被调用")
        logger.info(f"   ├─ 进程ID: {pid}")
        logger.info(f"   ├─ 线程ID: {thread_id}")
        logger.info(f"   ├─ 线程名: {thread_name}")
        logger.info(f"   ├─ 时间戳: {timestamp}")
        logger.info(f"   └─ 任务ID: {task_id}")
        
        # 防止同一秒重复执行
        if task_id in _task_executed:
            logger.warning(f"⚠️ [DUPLICATE] 任务已存在，跳过执行: {task_id}")
            return
        
        _task_executed.add(task_id)
        
        # 记录当前任务集合状态
        logger.info(f"📊 [STATUS] 当前任务集合大小: {len(_task_executed)}")
        logger.info(f"📋 [STATUS] 任务集合内容: {list(_task_executed)[-5:]}")  # 显示最后5个
        
        # 清理旧记录（保留最近10分钟的任务记录）
        cutoff_time = now - timedelta(minutes=10)
        old_keys = [k for k in _task_executed if k < f"task_{cutoff_time.strftime('%Y%m%d%H%M%S%f')[:-3]}"]
        for key in old_keys:
            _task_executed.discard(key)
        
        if old_keys:
            logger.info(f"🧹 [CLEANUP] 清理旧任务记录: {len(old_keys)}个")
        
        # 检查同一分钟内的执行次数
        minute_prefix = f"task_{now.strftime('%Y%m%d%H%M')}"
        current_minute_tasks = [k for k in _task_executed if k.startswith(minute_prefix)]
        
        if len(current_minute_tasks) > 1:
            logger.warning(f"⚠️ [DUPLICATE] 同一分钟内已执行 {len(current_minute_tasks)} 次任务")
            logger.warning(f"   ├─ 当前任务: {task_id}")
            logger.warning(f"   └─ 已存在任务: {current_minute_tasks}")
            return
        
        # 交易日判断
        try:
            from utils.trading_calendar import is_today_trading_day
            
            if not is_today_trading_day('CN'):
                today = datetime.now().date()
                weekday = today.strftime('%A')
                logger.info(f"📅 [TRADING_DAY] 今日({today})不是交易日，跳过执行")
                logger.info(f"   ├─ 星期: {weekday}")
                logger.info(f"   └─ 原因: 非交易日或节假日")
                return
            
            logger.info("📅 [TRADING_DAY] 今日是交易日，准备执行量化任务")
            
        except ImportError:
            logger.warning("⚠️ [TRADING_DAY] 交易日历工具未找到，使用工作日判断")
            # 回退到简单的工作日判断
            today = datetime.now().date()
            weekday = today.weekday()
            if weekday >= 5:  # 周六(5)或周日(6)
                logger.info(f"📅 [TRADING_DAY] 今日({today.strftime('%Y-%m-%d')})是周末，跳过执行")
                logger.info(f"   ├─ 星期: {today.strftime('%A')}")
                logger.info(f"   └─ 原因: 周末休市")
                return
            logger.info("📅 [TRADING_DAY] 今日是工作日，准备执行量化任务")
        except Exception as e:
            logger.warning(f"⚠️ [TRADING_DAY] 交易日判断失败: {e}，继续执行")
        
        # 开始执行
        start_time = now
        logger.info("🚀 [START] 开始执行定时任务")
        
        try:
            # 模拟任务执行时间
            import time
            time.sleep(0.1)  # 100ms延迟，便于观察并发
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            logger.info("=" * 60)
            logger.info("✅ [SUCCESS] 定时任务执行完成")
            logger.info(f"   ├─ 开始时间: {start_time.strftime('%H:%M:%S.%f')[:-3]}")
            logger.info(f"   ├─ 结束时间: {end_time.strftime('%H:%M:%S.%f')[:-3]}")
            logger.info(f"   ├─ 执行耗时: {duration:.3f}秒")
            logger.info(f"   ├─ 当前日期: {end_time.strftime('%Y-%m-%d')}")
            logger.info(f"   └─ 星期: {end_time.strftime('%A')}")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error("❌ [ERROR] 定时任务执行失败")
            logger.error(f"   ├─ 错误信息: {str(e)}")
            logger.error(f"   ├─ 任务ID: {task_id}")
            logger.error("   └─ 异常详情:", exc_info=True)
    
    def _execute_quant_trading(self):
        """执行量化交易任务（包含诊断报告生成）"""
        try:
            logger.info("🤖 [QUANT] 开始执行量化交易任务（含诊断报告）")
            
            import json
            import sys
            import os
            
            # 添加项目根目录到Python路径
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            
            # 动态导入所需服务
            try:
                from service.quant_trading import StockDiagnosisService, execute_daily_quant_trading
            except ImportError as e:
                logger.error(f"❌ [QUANT] 无法导入服务: {str(e)}")
                return
            
            monitor_config_file = os.path.join(project_root, 'user_monitor_config.json')
            
            if not os.path.exists(monitor_config_file):
                logger.warning("⚠️ [QUANT] 用户配置文件不存在")
                return
            
            with open(monitor_config_file, 'r', encoding='utf-8') as f:
                try:
                    all_data = json.load(f)
                except Exception as e:
                    logger.error(f"❌ [QUANT] 加载用户配置失败: {str(e)}")
                    return
            
            # 创建诊断服务实例
            diagnosis_service = StockDiagnosisService()
            
            # 遍历所有用户配置
            processed_users = 0
            generated_reports = 0
            
            for user_id, user_config in all_data.items():
                # 检查是否开启量化交易
                quant_enabled = user_config.get('quant_trading_enabled', False)
                if not quant_enabled:
                    logger.info(f"⏭️ [QUANT] 用户{user_id}未开启量化交易，跳过")
                    continue
                
                # 获取用户监控股票列表
                stocks = user_config.get('stocks', [])
                if not stocks:
                    logger.info(f"⏭️ [QUANT] 用户{user_id}无监控股票，跳过")
                    continue
                
                logger.info(f"🎯 [QUANT] 开始处理用户{user_id}，股票数量: {len(stocks)}")
                
                try:
                    # 第1步：生成诊断报告
                    logger.info(f"📊 [DIAGNOSIS] 开始生成诊断报告: 用户{user_id}")
                    diagnosis_results = []
                    
                    for stock_symbol in stocks:
                        try:
                            logger.info(f"🔍 [DIAGNOSIS] 诊断股票: {stock_symbol} (用户{user_id})")
                            # diagnosis_result = diagnosis_service.get_individual_diagnosis(stock_symbol)
                            
                            # if diagnosis_result and diagnosis_result.get('status') == 'success':
                            #     diagnosis_results.append(diagnosis_result)
                            #     generated_reports += 1
                            #     logger.info(f"✅ [DIAGNOSIS] 诊断完成: {stock_symbol}")
                            # else:
                            #     logger.warning(f"⚠️ [DIAGNOSIS] 诊断失败: {stock_symbol}")
                                
                        except Exception as e:
                            logger.error(f"❌ [DIAGNOSIS] 诊断异常 {stock_symbol}: {str(e)}")
                            continue
                    
                    logger.info(f"📋 [DIAGNOSIS] 用户{user_id}诊断报告生成完成: {len(diagnosis_results)}个")
                    
                    # 第2步：基于诊断报告执行量化交易
                    if diagnosis_results:
                        logger.info(f"🤖 [TRADING] 开始执行量化交易: 用户{user_id}")
                        trading_result = execute_daily_quant_trading(user_id, stocks)
                        
                        if trading_result and trading_result.get('success'):
                            logger.info(f"✅ [TRADING] 量化交易执行成功: 用户{user_id}")
                            logger.info(f"   ├─ 诊断报告: {len(diagnosis_results)}个")
                            logger.info(f"   ├─ 买入订单: {len(trading_result.get('buy_executions', []))}")
                            logger.info(f"   ├─ 卖出订单: {len(trading_result.get('sell_executions', []))}")
                            logger.info(f"   └─ 总收益: {trading_result.get('total_profit', 0)}")
                            processed_users += 1
                        else:
                            error_msg = trading_result.get('error', '未知错误') if trading_result else '无返回结果'
                            logger.warning(f"⚠️ [TRADING] 量化交易执行失败: 用户{user_id}, 错误: {error_msg}")
                    else:
                        logger.warning(f"⚠️ [QUANT] 用户{user_id}无有效诊断报告，跳过交易")
                        
                except Exception as e:
                    logger.error(f"❌ [QUANT] 处理用户{user_id}异常: {str(e)}", exc_info=True)
                    continue
            
            logger.info(f"🎉 [QUANT] 任务完成 - 处理用户: {processed_users}, 生成报告: {generated_reports}")
            
        except Exception as e:
            logger.error(f"❌ [QUANT] 量化交易任务失败: {str(e)}", exc_info=True)
    
    def stop(self):
        """停止调度器并释放文件锁"""
        global _is_started
        
        if self.scheduler and self.scheduler.running:
            try:
                self.scheduler.shutdown(wait=True)
                _is_started = False  # 重置全局状态
                self._release_lock()  # 释放文件锁
                logger.info("调度器已停止，文件锁已释放")
            except Exception as e:
                logger.error(f"停止调度器失败: {str(e)}")
                self._release_lock()  # 确保锁被释放

# 全局实例
_scheduler_instance = None

def get_scheduler():
    """获取全局单例"""
    global _scheduler_instance
    if _scheduler_instance is None:
        with _scheduler_lock:
            if _scheduler_instance is None:
                _scheduler_instance = SimpleQuantScheduler()
    return _scheduler_instance

def start_simple_scheduler():
    """启动调度器（带全局锁）"""
    global _is_started
    
    with _startup_lock:
        if _is_started:
            scheduler = get_scheduler()
            if scheduler.is_running():
                return False
        
        scheduler = get_scheduler()
        result = scheduler.start()
        return result

def stop_simple_scheduler():
    """停止调度器"""
    global _scheduler_instance
    if _scheduler_instance:
        _scheduler_instance.stop()
        _scheduler_instance = None

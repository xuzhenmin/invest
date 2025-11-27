"""
数据库导入管理类
用于将诊断报告、交易记录、未成交记录和持仓信息导入到数据库中
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend.service.storage.models import (
    DiagnosisReport, TradeRecord, TradeFailure, Position,
    RiskLevel, Recommendation
)
from backend.service.storage.data_service import data_service

logger = logging.getLogger(__name__)


class DatabaseImportManager:
    """数据库导入管理器"""
    
    def __init__(self):
        self.import_stats = {
            'diagnosis_reports': {'success': 0, 'failed': 0, 'errors': []},
            'trade_records': {'success': 0, 'failed': 0, 'errors': []},
            'trade_failures': {'success': 0, 'failed': 0, 'errors': []},
            'positions': {'success': 0, 'failed': 0, 'errors': []}
        }
    
    def reset_stats(self):
        """重置导入统计"""
        for key in self.import_stats:
            self.import_stats[key] = {'success': 0, 'failed': 0, 'errors': []}
    
    def get_import_stats(self) -> Dict[str, Any]:
        """获取导入统计信息"""
        return self.import_stats.copy()
    
    def import_diagnosis_reports(self, file_path: str, user_id: str = None) -> bool:
        """导入诊断报告
        
        Args:
            file_path: JSON文件路径
            user_id: 用户ID（可选）
            
        Returns:
            是否导入成功
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"文件不存在: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 支持单个报告或报告列表
            reports_data = data if isinstance(data, list) else [data]
            
            reports_to_save = []
            for report_data in reports_data:
                try:
                    report = self._create_diagnosis_report_from_data(report_data)
                    if report:
                        reports_to_save.append(report)
                except Exception as e:
                    self.import_stats['diagnosis_reports']['failed'] += 1
                    self.import_stats['diagnosis_reports']['errors'].append(str(e))
                    logger.error(f"诊断报告数据验证失败: {e}")
            
            if reports_to_save:
                data_service.batch_save_diagnosis_reports(reports_to_save)
                self.import_stats['diagnosis_reports']['success'] += len(reports_to_save)
                logger.info(f"成功导入 {len(reports_to_save)} 条诊断报告")
            
            return True
            
        except Exception as e:
            logger.error(f"导入诊断报告失败: {e}")
            self.import_stats['diagnosis_reports']['errors'].append(str(e))
            return False
    
    def import_trade_records(self, file_path: str, user_id: str = None) -> bool:
        """导入交易记录
        
        Args:
            file_path: JSON文件路径
            user_id: 用户ID（可选，如果数据中已包含则不需要）
            
        Returns:
            是否导入成功
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"文件不存在: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 支持单个记录或记录列表
            records_data = data if isinstance(data, list) else [data]
            
            records_to_save = []
            for record_data in records_data:
                try:
                    record = self._create_trade_record_from_data(record_data, user_id)
                    if record:
                        records_to_save.append(record)
                except Exception as e:
                    self.import_stats['trade_records']['failed'] += 1
                    self.import_stats['trade_records']['errors'].append(str(e))
                    logger.error(f"交易记录数据验证失败: {e}")
            
            if records_to_save:
                data_service.batch_save_trade_records(records_to_save)
                self.import_stats['trade_records']['success'] += len(records_to_save)
                logger.info(f"成功导入 {len(records_to_save)} 条交易记录")
            
            return True
            
        except Exception as e:
            logger.error(f"导入交易记录失败: {e}")
            self.import_stats['trade_records']['errors'].append(str(e))
            return False
    
    def import_trade_failures(self, file_path: str, user_id: str = None) -> bool:
        """导入交易失败记录
        
        Args:
            file_path: JSON文件路径
            user_id: 用户ID（可选，如果数据中已包含则不需要）
            
        Returns:
            是否导入成功
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"文件不存在: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 支持单个记录或记录列表
            failures_data = data if isinstance(data, list) else [data]
            
            failures_to_save = []
            for failure_data in failures_data:
                try:
                    failure = self._create_trade_failure_from_data(failure_data, user_id)
                    if failure:
                        failures_to_save.append(failure)
                except Exception as e:
                    self.import_stats['trade_failures']['failed'] += 1
                    self.import_stats['trade_failures']['errors'].append(str(e))
                    logger.error(f"交易失败数据验证失败: {e}")
            
            if failures_to_save:
                data_service.batch_save_trade_failures(failures_to_save)
                self.import_stats['trade_failures']['success'] += len(failures_to_save)
                logger.info(f"成功导入 {len(failures_to_save)} 条交易失败记录")
            
            return True
            
        except Exception as e:
            logger.error(f"导入交易失败记录失败: {e}")
            self.import_stats['trade_failures']['errors'].append(str(e))
            return False
    
    def import_positions(self, file_path: str, user_id: str = None) -> bool:
        """导入持仓信息
        
        Args:
            file_path: JSON文件路径
            user_id: 用户ID（可选，如果数据中已包含则不需要）
            
        Returns:
            是否导入成功
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"文件不存在: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 支持单个持仓或持仓列表
            positions_data = data if isinstance(data, list) else [data]
            
            positions_to_save = []
            for position_data in positions_data:
                try:
                    position = self._create_position_from_data(position_data, user_id)
                    if position:
                        positions_to_save.append(position)
                except Exception as e:
                    self.import_stats['positions']['failed'] += 1
                    self.import_stats['positions']['errors'].append(str(e))
                    logger.error(f"持仓数据验证失败: {e}")
            
            if positions_to_save:
                data_service.batch_save_positions(positions_to_save)
                self.import_stats['positions']['success'] += len(positions_to_save)
                logger.info(f"成功导入 {len(positions_to_save)} 条持仓信息")
            
            return True
            
        except Exception as e:
            logger.error(f"导入持仓信息失败: {e}")
            self.import_stats['positions']['errors'].append(str(e))
            return False
    
    def import_all_from_directory(self, directory_path: str, user_id: str = None) -> Dict[str, bool]:
        """从目录导入所有数据
        
        Args:
            directory_path: 数据目录路径
            user_id: 用户ID（可选）
            
        Returns:
            各类型数据导入结果
        """
        self.reset_stats()
        directory = Path(directory_path)
        
        if not directory.exists():
            logger.error(f"目录不存在: {directory_path}")
            return {}
        
        results = {}
        
        # 导入诊断报告
        diagnosis_files = list(directory.glob("**/diagnosis_reports*.json"))
        if diagnosis_files:
            results['diagnosis_reports'] = any(
                self.import_diagnosis_reports(str(f), user_id) for f in diagnosis_files
            )
        
        # 导入交易记录
        trade_files = list(directory.glob("**/trade_records*.json"))
        if trade_files:
            results['trade_records'] = any(
                self.import_trade_records(str(f), user_id) for f in trade_files
            )
        
        # 导入交易失败记录
        failure_files = list(directory.glob("**/trade_failures*.json"))
        if failure_files:
            results['trade_failures'] = any(
                self.import_trade_failures(str(f), user_id) for f in failure_files
            )
        
        # 导入持仓信息
        position_files = list(directory.glob("**/positions*.json"))
        if position_files:
            results['positions'] = any(
                self.import_positions(str(f), user_id) for f in position_files
            )
        
        return results
    
    def _create_diagnosis_report_from_data(self, data: Dict[str, Any]) -> Optional[DiagnosisReport]:
        """从数据创建诊断报告对象"""
        try:
            return DiagnosisReport(
                symbol=data['symbol'],
                name=data['name'],
                current_price=float(data['current_price']),
                overall_score=float(data['overall_score']),
                fundamental_score=float(data['fundamental_score']),
                technical_score=float(data['technical_score']),
                capital_score=float(data['capital_score']),
                valuation_score=float(data['valuation_score']),
                risk_level=data.get('risk_level', RiskLevel.MEDIUM.value),
                recommendation=data.get('recommendation', Recommendation.HOLD.value),
                target_price=float(data['target_price']) if data.get('target_price') else None,
                stop_loss=float(data['stop_loss']) if data.get('stop_loss') else None,
                support=float(data['support']) if data.get('support') else None,
                resistance=float(data['resistance']) if data.get('resistance') else None,
                buy_price=float(data['buy_price']) if data.get('buy_price') else None,
                sell_price=float(data['sell_price']) if data.get('sell_price') else None,
                investment_reason=data.get('investment_reason', ''),
                key_indicators=data.get('key_indicators'),
                risk_warnings=data.get('risk_warnings'),
                timestamp=datetime.fromisoformat(data['timestamp']) if data.get('timestamp') else datetime.now(),
                date=datetime.fromisoformat(data['date']).date() if data.get('date') else datetime.now().date()
            )
        except (KeyError, ValueError) as e:
            logger.error(f"诊断报告数据格式错误: {e}")
            return None
    
    def _create_trade_record_from_data(self, data: Dict[str, Any], user_id: str = None) -> Optional[TradeRecord]:
        """从数据创建交易记录对象"""
        try:
            return TradeRecord(
                user_id=data.get('user_id', user_id),
                symbol=data['symbol'],
                name=data['name'],
                action=data['action'],
                timestamp=datetime.fromisoformat(data['timestamp']) if data.get('timestamp') else datetime.now(),
                trade_date=datetime.fromisoformat(data['date']).date() if data.get('date') else datetime.now().date(),
                price=float(data['price']),
                quantity=int(data['quantity']),
                total_cost=float(data['total_cost']),
                order_id=data.get('order_id'),
                signal_data=data.get('signal_data')
            )
        except (KeyError, ValueError) as e:
            logger.error(f"交易记录数据格式错误: {e}")
            return None
    
    def _create_trade_failure_from_data(self, data: Dict[str, Any], user_id: str = None) -> Optional[TradeFailure]:
        """从数据创建交易失败对象"""
        try:
            return TradeFailure(
                user_id=data.get('user_id', user_id),
                symbol=data['symbol'],
                name=data['name'],
                action=data['action'],
                reason=data['reason'],
                timestamp=datetime.fromisoformat(data['timestamp']) if data.get('timestamp') else datetime.now(),
                trade_date=datetime.fromisoformat(data['date']).date() if data.get('date') else datetime.now().date(),
                signal_data=data.get('signal_data'),
                details=data.get('details')
            )
        except (KeyError, ValueError) as e:
            logger.error(f"交易失败数据格式错误: {e}")
            return None
    
    def _create_position_from_data(self, data: Dict[str, Any], user_id: str = None) -> Optional[Position]:
        """从数据创建持仓对象"""
        try:
            return Position(
                user_id=data.get('user_id', user_id),
                symbol=data['symbol'],
                name=data['name'],
                quantity=int(data['quantity']),
                avg_price=float(data['avg_price']),
                total_cost=float(data['total_cost']),
                market_value=float(data['market_value']) if data.get('market_value') else float(data['quantity']) * float(data['avg_price']),
                floating_pnl=float(data.get('floating_pnl', 0)),
                floating_pnl_ratio=float(data.get('floating_pnl_ratio', 0)),
                last_price=float(data['last_price']) if data.get('last_price') else float(data['avg_price']),
                updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else datetime.now(),
                created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else datetime.now()
            )
        except (KeyError, ValueError) as e:
            logger.error(f"持仓数据格式错误: {e}")
            return None


# 全局导入管理器实例
import_manager = DatabaseImportManager()

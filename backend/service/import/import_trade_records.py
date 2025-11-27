#!/usr/bin/env python3
"""
交易记录导入脚本
用于导入成交记录和未成交记录到数据库
"""

import json
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# 添加项目根目录到路径
sys.path.append('/Users/zhenmin/mywork/quant-py')

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend.service.storage.models import TradeRecord, TradeFailure
from backend.service.storage.data_service import data_service

class TradeRecordsImporter:
    """交易记录导入器"""
    
    def __init__(self):
        self.stats = {
            'executed_orders': {'success': 0, 'failed': 0, 'errors': []},
            'unmet_conditions': {'success': 0, 'failed': 0, 'errors': []}
        }
    
    def reset_stats(self):
        """重置导入统计"""
        self.stats = {
            'executed_orders': {'success': 0, 'failed': 0, 'errors': []},
            'unmet_conditions': {'success': 0, 'failed': 0, 'errors': []}
        }
    
    def import_executed_orders(self, file_path: str, user_id: str = None) -> bool:
        """导入成交记录
        
        Args:
            file_path: 成交记录文件路径
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
            
            # 支持单个记录或记录列表
            orders_data = data if isinstance(data, list) else [data]
            
            success_count = 0
            for record_data in orders_data:
                try:
                    record = self._create_trade_record_from_data(record_data, user_id)
                    if record:
                        record_id = data_service.save_trade_record(record)
                        if record_id > 0:
                            success_count += 1
                        else:
                            self.stats['executed_orders']['failed'] += 1
                            self.stats['executed_orders']['errors'].append("保存失败")
                except Exception as e:
                    self.stats['executed_orders']['failed'] += 1
                    self.stats['executed_orders']['errors'].append(str(e))
                    print(f"成交记录数据验证失败: {e}")
            
            self.stats['executed_orders']['success'] += success_count
            print(f"成功导入 {success_count} 条成交记录")
            
            return True
            
        except Exception as e:
            print(f"导入成交记录失败: {e}")
            self.stats['executed_orders']['errors'].append(str(e))
            return False
    
    def import_unmet_conditions(self, file_path: str, user_id: str = None) -> bool:
        """导入未成交记录
        
        Args:
            file_path: 未成交记录文件路径
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
            
            # 支持单个记录或记录列表
            conditions_data = data if isinstance(data, list) else [data]
            
            success_count = 0
            for failure_data in conditions_data:
                try:
                    failure = self._create_trade_failure_from_data(failure_data, user_id)
                    if failure:
                        record_id = data_service.save_trade_failure(failure)
                        if record_id > 0:
                            success_count += 1
                        else:
                            self.stats['unmet_conditions']['failed'] += 1
                            self.stats['unmet_conditions']['errors'].append("保存失败")
                except Exception as e:
                    self.stats['unmet_conditions']['failed'] += 1
                    self.stats['unmet_conditions']['errors'].append(str(e))
                    print(f"交易失败数据验证失败: {e}")
            
            self.stats['unmet_conditions']['success'] += success_count
            print(f"成功导入 {success_count} 条未成交记录")
            
            return True
            
        except Exception as e:
            print(f"导入未成交记录失败: {e}")
            self.stats['unmet_conditions']['errors'].append(str(e))
            return False
    
    def import_all_from_directory(self, directory_path: str, user_id: str = None) -> Dict[str, int]:
        """从目录导入所有交易记录（包括所有日期的文件）
        
        Args:
            directory_path: 数据目录路径
            user_id: 用户ID（可选）
            
        Returns:
            导入统计信息
        """
        self.reset_stats()
        directory = Path(directory_path)
        
        if not directory.exists():
            print(f"目录不存在: {directory_path}")
            return {}
        
        # 获取所有成交记录文件（包括子目录）
        executed_files = list(directory.rglob("executed_orders_*.json"))
        print(f"找到 {len(executed_files)} 个成交记录文件")
        
        # 获取所有未成交记录文件（包括子目录）
        unmet_files = list(directory.rglob("unmet_conditions_*.json"))
        print(f"找到 {len(unmet_files)} 个未成交记录文件")
        
        # 按日期排序处理文件
        executed_files.sort(key=lambda x: x.stem.split('_')[-1])
        unmet_files.sort(key=lambda x: x.stem.split('_')[-1])
        
        # 导入所有成交记录
        for file_path in executed_files:
            date_str = file_path.stem.split('_')[-1]
            print(f"正在导入成交记录: {date_str}")
            self.import_executed_orders(str(file_path), user_id)
        
        # 导入所有未成交记录
        for file_path in unmet_files:
            date_str = file_path.stem.split('_')[-1]
            print(f"正在导入未成交记录: {date_str}")
            self.import_unmet_conditions(str(file_path), user_id)
        
        return {
            'executed_orders': self.stats['executed_orders']['success'],
            'unmet_conditions': self.stats['unmet_conditions']['success'],
            'executed_files': len(executed_files),
            'unmet_files': len(unmet_files),
            'total_files': len(executed_files) + len(unmet_files)
        }
    
    def get_import_stats(self) -> Dict[str, Any]:
        """获取导入统计信息"""
        return self.stats.copy()
    
    def _create_trade_record_from_data(self, data: Dict[str, Any], user_id: str = None) -> TradeRecord:
        """从数据创建交易记录对象"""
        try:
            # 从signal_data中获取name，如果没有则使用symbol
            name = data.get('name')
            if not name and 'signal_data' in data:
                name = data['signal_data'].get('name', data['symbol'])
            if not name:
                name = data['symbol']
            
            return TradeRecord(
                user_id=data.get('user_id', user_id or 'default_user'),
                symbol=data['symbol'],
                name=name,
                action=data['action'],
                timestamp=datetime.fromisoformat(data['timestamp']),
                trade_date=datetime.fromisoformat(data['date']).date(),
                price=float(data['price']),
                quantity=int(data['quantity']),
                total_cost=float(data['total_cost']),
                order_id=data.get('order_id'),
                signal_data=data.get('signal_data')
            )
        except (KeyError, ValueError) as e:
            print(f"交易记录数据格式错误: {e}")
            raise
    
    def _create_trade_failure_from_data(self, data: Dict[str, Any], user_id: str = None) -> TradeFailure:
        """从数据创建交易失败对象"""
        try:
            signal_data = data.get('signal_data', {})
            name = signal_data.get('name', data.get('name', '未知股票'))
            
            # 处理user_id为null的情况
            record_user_id = data.get('user_id', user_id)
            if record_user_id is None:
                record_user_id = 'zhenmin'  # 使用默认用户
            
            return TradeFailure(
                user_id=record_user_id,
                symbol=data['symbol'],
                name=name,
                action=data['action'],
                reason=data['reason'],
                timestamp=datetime.fromisoformat(data['timestamp']),
                trade_date=datetime.fromisoformat(data['date']).date(),
                signal_data=data.get('signal_data'),
                details=data.get('details')
            )
        except (KeyError, ValueError) as e:
            print(f"交易失败数据格式错误: {e}")
            raise


def main():
    """主函数 - 优化为导入所有文件"""
    importer = TradeRecordsImporter()
    
    # 导入所有交易记录
    directory_path = "backend/trade_records"
    print(f"开始导入所有交易记录: {directory_path}")
    
    stats = importer.import_all_from_directory(directory_path)
    
    print("\n=== 导入完成统计 ===")
    print(f"处理文件总数: {stats.get('total_files', 0)} 个")
    print(f"成交记录: 成功导入 {stats.get('executed_orders', 0)} 条")
    print(f"未成交记录: 成功导入 {stats.get('unmet_conditions', 0)} 条")
    print(f"成交记录文件: {stats.get('executed_files', 0)} 个")
    print(f"未成交记录文件: {stats.get('unmet_files', 0)} 个")
    
    # 详细统计
    detailed_stats = importer.get_import_stats()
    if detailed_stats['executed_orders']['errors']:
        print("成交记录错误:", detailed_stats['executed_orders']['errors'])
    if detailed_stats['unmet_conditions']['errors']:
        print("未成交记录错误:", detailed_stats['unmet_conditions']['errors'])


if __name__ == "__main__":
    main()

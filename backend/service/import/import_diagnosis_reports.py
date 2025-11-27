#!/usr/bin/env python3
"""
诊断报告导入脚本
专门处理诊断报告的特殊数据结构
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
sys.path.append('/Users/zhenmin/mywork/quant-py')

from backend.service.storage import data_service
from backend.service.storage.models import DiagnosisReport

def import_diagnosis_reports():
    """导入诊断报告数据"""
    file_path = Path('backend/diagnosis_reports/diagnosis_reports.json')
    
    if not file_path.exists():
        print(f"文件不存在: {file_path}")
        return False
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        reports_to_save = []
        success_count = 0
        error_count = 0
        
        # 遍历日期
        for date_str, stocks_data in data.items():
            print(f"处理日期: {date_str}")
            
            # 遍历股票
            for symbol, stock_data in stocks_data.items():
                try:
                    diagnosis_data = stock_data['diagnosis']
                    
                    # 处理关键指标和风险提示
                    key_indicators = diagnosis_data.get('key_indicators', [])
                    risk_warnings = diagnosis_data.get('risk_warnings', [])
                    
                    # 创建诊断报告对象
                    report = DiagnosisReport(
                        symbol=diagnosis_data['symbol'],
                        name=diagnosis_data['name'],
                        current_price=float(diagnosis_data['current_price']),
                        overall_score=float(diagnosis_data['overall_score']),
                        fundamental_score=float(diagnosis_data['fundamental_score']),
                        technical_score=float(diagnosis_data['technical_score']),
                        capital_score=float(diagnosis_data['capital_score']),
                        valuation_score=float(diagnosis_data['valuation_score']),
                        risk_level=diagnosis_data['risk_level'],
                        recommendation=diagnosis_data['recommendation'],
                        target_price=float(diagnosis_data['target_price']) if diagnosis_data.get('target_price') else None,
                        stop_loss=float(diagnosis_data['stop_loss']) if diagnosis_data.get('stop_loss') else None,
                        support=float(diagnosis_data['support']) if diagnosis_data.get('support') else None,
                        resistance=float(diagnosis_data['resistance']) if diagnosis_data.get('resistance') else None,
                        buy_price=float(diagnosis_data['buy_price']) if diagnosis_data.get('buy_price') else None,
                        sell_price=float(diagnosis_data['sell_price']) if diagnosis_data.get('sell_price') else None,
                        investment_reason=diagnosis_data['investment_reason'],
                        key_indicators=key_indicators,
                        risk_warnings=risk_warnings,
                        timestamp=datetime.fromisoformat(diagnosis_data['timestamp']),
                        date=datetime.fromisoformat(date_str).date()
                    )
                    
                    reports_to_save.append(report)
                    success_count += 1
                    
                    if success_count % 10 == 0:
                        print(f"已处理 {success_count} 条记录...")
                        
                except Exception as e:
                    print(f"处理股票 {symbol} 时出错: {e}")
                    error_count += 1
        
        # 批量保存
        if reports_to_save:
            data_service.batch_save_diagnosis_reports(reports_to_save)
            print(f"成功导入 {success_count} 条诊断报告")
            print(f"失败 {error_count} 条")
        
        return True
        
    except Exception as e:
        print(f"导入失败: {e}")
        return False

if __name__ == "__main__":
    result = import_diagnosis_reports()
    print("导入完成" if result else "导入失败")

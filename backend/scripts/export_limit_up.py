"""
导出涨停历史数据到 JSON 文件。
在旧服务器上运行：python scripts/export_limit_up.py [输出文件路径]
"""
import json
import os
import sys
from datetime import datetime

# 确保能找到 backend 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

from service.storage.database_manager import db_manager

def export_data(output_path: str):
    daily_rows = db_manager.execute_query(
        "SELECT * FROM limit_up_daily ORDER BY trade_date ASC, stock_code ASC"
    )
    stats_rows = db_manager.execute_query(
        "SELECT * FROM limit_up_market_stats ORDER BY trade_date ASC"
    )

    def rows_to_dicts(rows):
        if not rows:
            return []
        return [dict(r) for r in rows]

    daily = rows_to_dicts(daily_rows)
    stats = rows_to_dicts(stats_rows)

    payload = {
        'exported_at': datetime.now().isoformat(),
        'limit_up_daily': daily,
        'limit_up_market_stats': stats,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"导出完成：limit_up_daily {len(daily)} 条，limit_up_market_stats {len(stats)} 条")
    print(f"文件：{output_path}")

if __name__ == '__main__':
    output = sys.argv[1] if len(sys.argv) > 1 else 'limit_up_export.json'
    export_data(output)

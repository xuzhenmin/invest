"""
将导出的涨停历史数据导入到目标服务器的数据库中。
在新服务器上运行：python scripts/import_limit_up.py [JSON文件路径]

默认策略：INSERT OR IGNORE（已存在的记录不覆盖）
加 --overwrite 参数：INSERT OR REPLACE（已存在的记录覆盖）
"""
import json
import os
import sys
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

from service.storage.database_manager import db_manager

DAILY_FIELDS = [
    'trade_date', 'stock_code', 'stock_name', 'market', 'industry',
    'close_price', 'change_pct', 'first_limit_time', 'limit_order_amount',
    'turnover_rate', 'market_cap', 'consecutive_days', 'is_new', 'is_yizi_ban',
]

STATS_FIELDS = ['trade_date', 'advance_count', 'decline_count', 'flat_count']


def ensure_tables():
    db_manager.execute_update("""
        CREATE TABLE IF NOT EXISTS limit_up_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date TEXT NOT NULL,
            stock_code TEXT NOT NULL,
            stock_name TEXT DEFAULT '',
            market TEXT DEFAULT '',
            industry TEXT DEFAULT '',
            close_price REAL DEFAULT 0,
            change_pct REAL DEFAULT 0,
            first_limit_time TEXT DEFAULT '',
            limit_order_amount TEXT DEFAULT '',
            turnover_rate REAL DEFAULT 0,
            market_cap TEXT DEFAULT '',
            consecutive_days INTEGER DEFAULT 1,
            is_new INTEGER DEFAULT 0,
            is_yizi_ban INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(trade_date, stock_code)
        )
    """)
    db_manager.execute_update(
        "CREATE INDEX IF NOT EXISTS idx_limit_up_daily_date ON limit_up_daily(trade_date)"
    )
    db_manager.execute_update("""
        CREATE TABLE IF NOT EXISTS limit_up_market_stats (
            trade_date TEXT PRIMARY KEY,
            advance_count INTEGER DEFAULT 0,
            decline_count INTEGER DEFAULT 0,
            flat_count INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)


def import_data(input_path: str, overwrite: bool = False):
    with open(input_path, 'r', encoding='utf-8') as f:
        payload = json.load(f)

    daily_rows = payload.get('limit_up_daily', [])
    stats_rows = payload.get('limit_up_market_stats', [])
    exported_at = payload.get('exported_at', '未知')

    print(f"数据来源导出时间：{exported_at}")
    print(f"待导入：limit_up_daily {len(daily_rows)} 条，limit_up_market_stats {len(stats_rows)} 条")

    ensure_tables()

    conflict = "REPLACE" if overwrite else "IGNORE"

    # 导入 limit_up_daily
    daily_ok = daily_skip = 0
    batch = []
    for row in daily_rows:
        vals = tuple(row.get(f) for f in DAILY_FIELDS)
        batch.append(vals)
        if len(batch) >= 500:
            placeholders = ','.join(['?'] * len(DAILY_FIELDS))
            cols = ','.join(DAILY_FIELDS)
            db_manager.execute_many(
                f"INSERT OR {conflict} INTO limit_up_daily ({cols}) VALUES ({placeholders})",
                batch
            )
            batch = []
    if batch:
        placeholders = ','.join(['?'] * len(DAILY_FIELDS))
        cols = ','.join(DAILY_FIELDS)
        db_manager.execute_many(
            f"INSERT OR {conflict} INTO limit_up_daily ({cols}) VALUES ({placeholders})",
            batch
        )
    print(f"limit_up_daily 导入完成（策略: OR {conflict}）")

    # 导入 limit_up_market_stats
    stats_batch = []
    for row in stats_rows:
        vals = tuple(row.get(f) for f in STATS_FIELDS)
        stats_batch.append(vals)
    if stats_batch:
        placeholders = ','.join(['?'] * len(STATS_FIELDS))
        cols = ','.join(STATS_FIELDS)
        db_manager.execute_many(
            f"INSERT OR {conflict} INTO limit_up_market_stats ({cols}) VALUES ({placeholders})",
            stats_batch
        )
    print(f"limit_up_market_stats 导入完成（策略: OR {conflict}）")

    # 统计实际条数
    daily_count = db_manager.execute_query("SELECT COUNT(*) as c FROM limit_up_daily")[0]['c']
    stats_count = db_manager.execute_query("SELECT COUNT(*) as c FROM limit_up_market_stats")[0]['c']
    print(f"\n数据库现有：limit_up_daily {daily_count} 条，limit_up_market_stats {stats_count} 条")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='导入涨停历史数据')
    parser.add_argument('input', nargs='?', default='limit_up_export.json', help='JSON 文件路径')
    parser.add_argument('--overwrite', action='store_true', help='已存在的记录强制覆盖（默认跳过）')
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"文件不存在：{args.input}")
        sys.exit(1)

    import_data(args.input, overwrite=args.overwrite)

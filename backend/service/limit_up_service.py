"""每日涨停数据采集与分析服务"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from service.storage.database_manager import db_manager

logger = logging.getLogger(__name__)


class LimitUpService:
    """涨停股票采集、连板计算、新增/退出对比"""

    def __init__(self):
        self._ensure_table()
        self._industry_cache: Dict[str, str] = {}

    def _ensure_table(self):
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
        for col_def in [
            "ALTER TABLE limit_up_daily ADD COLUMN industry TEXT DEFAULT ''",
            "ALTER TABLE limit_up_daily ADD COLUMN is_yizi_ban INTEGER DEFAULT 0",
        ]:
            try:
                db_manager.execute_update(col_def)
            except Exception:
                pass
        db_manager.execute_update(
            "CREATE INDEX IF NOT EXISTS idx_limit_up_daily_date ON limit_up_daily(trade_date)")
        db_manager.execute_update("""
            CREATE TABLE IF NOT EXISTS limit_up_market_stats (
                trade_date TEXT PRIMARY KEY,
                advance_count INTEGER DEFAULT 0,
                decline_count INTEGER DEFAULT 0,
                flat_count INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT (datetime('now','localtime'))
            )
        """)

    def collect_today(self, date: str = None) -> dict:
        """采集指定日期（默认今日）涨停数据并持久化"""
        from service.datapip.miaoxiang_client import MiaoXiangClient

        target_date = date or datetime.now().strftime('%Y-%m-%d')

        try:
            from utils.trading_calendar import TradingCalendar
            td = datetime.strptime(target_date, '%Y-%m-%d').date()
            if not TradingCalendar.is_trading_day(td, 'CN'):
                logger.info(f"[LimitUp] {target_date} 非交易日，跳过采集")
                return {'date': target_date, 'skipped': True, 'reason': 'non_trading_day'}
        except Exception as e:
            logger.warning(f"[LimitUp] 交易日校验失败: {e}，继续采集")

        prev_date = self._get_prev_trading_date(target_date)

        if date:
            d = datetime.strptime(date, '%Y-%m-%d')
            query = f"{d.year}年{d.month}月{d.day}日涨停的A股"
        else:
            query = "今日涨停的A股"

        try:
            mx = MiaoXiangClient()
            today_stocks = mx.select_stocks_normalized(query)
        except Exception as e:
            logger.error(f"[LimitUp] 获取涨停数据失败({target_date}): {e}")
            return {'error': str(e)}

        if not today_stocks:
            return {'date': target_date, 'total': 0, 'collected': 0}

        prev_records = self._get_records_by_date(prev_date) if prev_date else []
        prev_codes = {r['stock_code']: r for r in prev_records}

        all_codes = []
        for stock in today_stocks:
            code = stock.get('code', '')
            market = stock.get('market', '')
            if code:
                all_codes.append(f"{code}.{market}" if market else code)
        industry_map = self._batch_get_industries(all_codes)

        records_to_save = []
        for stock in today_stocks:
            code = stock.get('code', '')
            if not code:
                continue
            market = stock.get('market', '')
            full_code = f"{code}.{market}" if market else code

            if full_code in prev_codes:
                consecutive = prev_codes[full_code].get('consecutive_days', 1) + 1
                is_new = 0
            else:
                consecutive = 1
                is_new = 1

            records_to_save.append({
                'trade_date': target_date,
                'stock_code': full_code,
                'stock_name': stock.get('name', ''),
                'market': market,
                'industry': industry_map.get(full_code, ''),
                'close_price': self._to_float(stock.get('price', 0)),
                'change_pct': self._to_float(stock.get('change_pct', 0)),
                'first_limit_time': stock.get('first_limit_time', '') or '',
                'limit_order_amount': str(stock.get('limit_order_amount', '') or ''),
                'turnover_rate': self._to_float(stock.get('turnover_rate', 0)),
                'market_cap': str(stock.get('market_cap', '') or ''),
                'consecutive_days': consecutive,
                'is_new': is_new,
                'is_yizi_ban': 1 if stock.get('is_yizi_ban') else 0,
            })

        self._batch_save(records_to_save)

        try:
            mx2 = MiaoXiangClient()
            breadth = mx2.get_market_breadth()
            db_manager.execute_update(
                """INSERT OR REPLACE INTO limit_up_market_stats
                   (trade_date, advance_count, decline_count, flat_count)
                   VALUES (?, ?, ?, ?)""",
                (target_date, breadth['advance'], breadth['decline'], breadth.get('flat', 0))
            )
        except Exception as e:
            logger.warning(f"[LimitUp] 涨跌家数采集失败: {e}")

        logger.info(f"[LimitUp] {target_date} 采集完成: {len(records_to_save)} 只涨停")
        return {
            'date': target_date,
            'total': len(records_to_save),
            'new_count': sum(1 for r in records_to_save if r['is_new']),
            'collected': len(records_to_save),
        }

    def backfill(self, days: int = 10) -> List[dict]:
        """回补最近 N 个交易日的涨停数据"""
        import time

        dates = []
        d = datetime.now()
        while len(dates) < days:
            d -= timedelta(days=1)
            if d.weekday() < 5:
                dates.append(d.strftime('%Y-%m-%d'))

        dates.reverse()

        results = []
        for date in dates:
            existing = self._get_records_by_date(date)
            if existing:
                results.append({'date': date, 'total': len(existing), 'skipped': True})
                continue

            result = self.collect_today(date)
            results.append(result)
            time.sleep(1)

        self.recalculate_consecutive()
        return results

    def recalculate_consecutive(self) -> dict:
        """重新计算所有记录的连板数"""
        all_dates = db_manager.execute_query(
            "SELECT DISTINCT trade_date FROM limit_up_daily ORDER BY trade_date ASC"
        )
        if not all_dates:
            return {'updated': 0}

        dates = [r['trade_date'] for r in all_dates]
        total_updated = 0
        prev_codes = {}

        for date in dates:
            records = self._get_records_by_date(date)
            current_codes = {}

            for r in records:
                code = r['stock_code']
                if code in prev_codes:
                    new_consecutive = prev_codes[code] + 1
                    new_is_new = 0
                else:
                    new_consecutive = 1
                    new_is_new = 1

                current_codes[code] = new_consecutive

                if r.get('consecutive_days') != new_consecutive or r.get('is_new') != new_is_new:
                    db_manager.execute_update(
                        "UPDATE limit_up_daily SET consecutive_days = ?, is_new = ? WHERE trade_date = ? AND stock_code = ?",
                        (new_consecutive, new_is_new, date, code)
                    )
                    total_updated += 1

            prev_codes = current_codes

        return {'dates': len(dates), 'updated': total_updated}

    def get_daily_summary(self, date: str = None) -> dict:
        """获取某日涨停复盘数据"""
        if not date:
            date = self._latest_trading_date()

        prev_date = self._get_prev_trading_date(date)
        today_records = self._get_records_by_date(date)
        prev_records = self._get_records_by_date(prev_date) if prev_date else []

        today_codes = {r['stock_code'] for r in today_records}
        prev_codes = {r['stock_code'] for r in prev_records}

        exit_codes = prev_codes - today_codes
        exit_stocks = [r for r in prev_records if r['stock_code'] in exit_codes]

        by_consecutive = {}
        for r in today_records:
            days = r.get('consecutive_days', 1)
            item = dict(r)
            item['is_exit'] = 0
            by_consecutive.setdefault(days, []).append(item)

        for r in exit_stocks:
            days = r.get('consecutive_days', 1)
            item = dict(r)
            item['is_exit'] = 1
            by_consecutive.setdefault(days, []).append(item)

        for days in by_consecutive:
            by_consecutive[days].sort(key=lambda x: (x['is_exit'], x.get('first_limit_time', '')))

        new_stocks = [r for r in today_records if r.get('is_new', 0)]

        by_industry = {}
        for r in today_records:
            ind = r.get('industry', '')
            if not ind:
                continue
            by_industry.setdefault(ind, []).append(r)

        prev_by_industry = {}
        for r in prev_records:
            ind = r.get('industry', '')
            if not ind:
                continue
            prev_by_industry.setdefault(ind, []).append(r)

        all_industries = set(list(by_industry.keys()) + list(prev_by_industry.keys()))
        industry_trend = []
        for ind in all_industries:
            today_count = len(by_industry.get(ind, []))
            prev_count = len(prev_by_industry.get(ind, []))
            industry_trend.append({
                'industry': ind,
                'today_count': today_count,
                'prev_count': prev_count,
                'change': today_count - prev_count,
                'stocks': [{'stock_name': s.get('stock_name', ''), 'stock_code': s.get('stock_code', ''),
                            'consecutive_days': s.get('consecutive_days', 1)}
                           for s in by_industry.get(ind, [])],
            })
        industry_trend.sort(key=lambda x: (-x['today_count'], -x['change']))

        exit_by_industry = {}
        for r in exit_stocks:
            ind = r.get('industry', '')
            if not ind:
                continue
            exit_by_industry.setdefault(ind, []).append(r)
        industry_exit_trend = [
            {'industry': ind, 'count': len(stocks),
             'today_count': len(by_industry.get(ind, [])),
             'stocks': [{'stock_name': s.get('stock_name', ''), 'stock_code': s.get('stock_code', '')} for s in stocks]}
            for ind, stocks in exit_by_industry.items()
        ]
        industry_exit_trend.sort(key=lambda x: -x['count'])

        return {
            'date': date,
            'prev_date': prev_date,
            'total_count': len(today_records),
            'new_count': len(new_stocks),
            'exit_count': len(exit_stocks),
            'by_consecutive': by_consecutive,
            'new_stocks': new_stocks,
            'exit_stocks': exit_stocks,
            'max_consecutive': max((r.get('consecutive_days', 1) for r in today_records), default=0),
            'industry_trend': industry_trend,
            'industry_exit_trend': industry_exit_trend,
            **self._get_market_breadth(date),
        }

    def get_trend(self, days: int = 15) -> List[dict]:
        """获取近 N 个交易日涨停数量趋势"""
        rows = db_manager.execute_query(
            """SELECT trade_date,
                      COUNT(*) as total,
                      SUM(CASE WHEN is_new=1 THEN 1 ELSE 0 END) as new_count
               FROM limit_up_daily
               GROUP BY trade_date
               ORDER BY trade_date DESC
               LIMIT ?""",
            (days,)
        )
        result = [{'trade_date': r['trade_date'], 'total': r['total'], 'new_count': r['new_count']}
                  for r in (rows or [])]
        result.reverse()
        return result

    # ── 内部方法 ──

    def _get_market_breadth(self, date: str) -> dict:
        rows = db_manager.execute_query(
            "SELECT advance_count, decline_count, flat_count FROM limit_up_market_stats WHERE trade_date = ?",
            (date,)
        )
        if rows:
            return {'advance_count': rows[0]['advance_count'], 'decline_count': rows[0]['decline_count'],
                    'flat_count': rows[0].get('flat_count', 0)}
        return {'advance_count': 0, 'decline_count': 0, 'flat_count': 0}

    def _latest_trading_date(self) -> str:
        """返回今天或最近的上一个交易日"""
        try:
            from utils.trading_calendar import TradingCalendar
            d = datetime.now().date()
            for _ in range(14):
                if TradingCalendar.is_trading_day(d, 'CN'):
                    return d.strftime('%Y-%m-%d')
                d -= timedelta(days=1)
        except Exception:
            pass
        # 兜底：从 DB 找最近有数据的日期
        rows = db_manager.execute_query(
            "SELECT DISTINCT trade_date FROM limit_up_daily ORDER BY trade_date DESC LIMIT 1"
        )
        if rows:
            return rows[0]['trade_date']
        return datetime.now().strftime('%Y-%m-%d')

    def _get_records_by_date(self, date: str) -> List[Dict[str, Any]]:
        if not date:
            return []
        rows = db_manager.execute_query(
            "SELECT * FROM limit_up_daily WHERE trade_date = ? ORDER BY consecutive_days DESC, first_limit_time ASC",
            (date,)
        )
        return rows or []

    def _batch_save(self, records: List[Dict]):
        if not records:
            return
        for r in records:
            db_manager.execute_update(
                """INSERT OR REPLACE INTO limit_up_daily
                   (trade_date, stock_code, stock_name, market, industry, close_price, change_pct,
                    first_limit_time, limit_order_amount, turnover_rate, market_cap,
                    consecutive_days, is_new, is_yizi_ban)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (r['trade_date'], r['stock_code'], r['stock_name'], r['market'],
                 r.get('industry', ''), r['close_price'], r['change_pct'], r['first_limit_time'],
                 r['limit_order_amount'], r['turnover_rate'], r['market_cap'],
                 r['consecutive_days'], r['is_new'], r.get('is_yizi_ban', 0))
            )

    def _get_prev_trading_date(self, date: str) -> Optional[str]:
        try:
            from utils.trading_calendar import TradingCalendar
            d = datetime.strptime(date, '%Y-%m-%d').date()
            for _ in range(14):
                d -= timedelta(days=1)
                if TradingCalendar.is_trading_day(d, 'CN'):
                    return d.strftime('%Y-%m-%d')
        except Exception:
            pass
        rows = db_manager.execute_query(
            "SELECT DISTINCT trade_date FROM limit_up_daily WHERE trade_date < ? ORDER BY trade_date DESC LIMIT 1",
            (date,)
        )
        if rows:
            return rows[0]['trade_date']
        return None

    def _batch_get_industries(self, stock_codes: List[str]) -> Dict[str, str]:
        result = {}
        missing = []
        for code in stock_codes:
            if code in self._industry_cache:
                result[code] = self._industry_cache[code]
            else:
                missing.append(code)

        if not missing:
            return result

        still_missing = []
        for code in missing:
            rows = db_manager.execute_query(
                "SELECT industry FROM limit_up_daily WHERE stock_code = ? AND industry != '' ORDER BY trade_date DESC LIMIT 1",
                (code,)
            )
            if rows and rows[0]['industry']:
                result[code] = rows[0]['industry']
                self._industry_cache[code] = rows[0]['industry']
            else:
                still_missing.append(code)
        missing = still_missing

        if not missing:
            return result

        try:
            from service.datapip.financial_data_client import FinancialDataClient
            client = FinancialDataClient()
            for i in range(0, len(missing), 20):
                batch = missing[i:i + 20]
                try:
                    resp = client.query([{
                        'url': '/api/v1/stock/component-list-belonged',
                        'params': {'symbols': batch}
                    }])
                    if not resp or not isinstance(resp, dict):
                        continue
                    for res_item in resp.get('results', []):
                        if not res_item.get('ok'):
                            continue
                        inner_results = res_item.get('data', {}).get('results', [])
                        for stock_result in inner_results:
                            meta = stock_result.get('meta', {})
                            fields = meta.get('fields', [])
                            data_rows = stock_result.get('data', [])
                            sym = stock_result.get('symbol', '')
                            if not fields or not data_rows:
                                continue
                            pt_idx = fields.index('plateType') if 'plateType' in fields else -1
                            pn_idx = fields.index('plateName') if 'plateName' in fields else -1
                            if pt_idx < 0 or pn_idx < 0:
                                continue
                            for row in data_rows:
                                if len(row) > max(pt_idx, pn_idx) and row[pt_idx] == 'plate_industry':
                                    if sym not in result:
                                        result[sym] = row[pn_idx]
                                        self._industry_cache[sym] = row[pn_idx]
                                    break
                except Exception as e:
                    logger.debug(f"[LimitUp] 行业查询批次失败: {e}")
        except Exception:
            pass

        return result

    @staticmethod
    def _to_float(val) -> float:
        if val is None:
            return 0.0
        if isinstance(val, (int, float)):
            return float(val)
        try:
            return float(str(val).replace(',', '').replace('%', ''))
        except (ValueError, TypeError):
            return 0.0


limit_up_service = LimitUpService()

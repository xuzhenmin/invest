"""数据采集层 — 聚合已有数据源为内容生成提供素材"""

import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

_STEP_TIMEOUT = 30


def _run_with_timeout(fn, timeout=_STEP_TIMEOUT, default=None):
    result_holder = [default]
    error_holder = [None]

    def wrapper():
        try:
            result_holder[0] = fn()
        except Exception as e:
            error_holder[0] = e

    t = threading.Thread(target=wrapper, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        logger.warning(f"[ContentCollector] 超时({timeout}s): {fn.__name__ if hasattr(fn, '__name__') else fn}")
        return default
    if error_holder[0]:
        logger.warning(f"[ContentCollector] 执行失败: {error_holder[0]}")
        return default
    return result_holder[0]


class ContentDataCollector:

    @staticmethod
    def _parse_v2_results(raw: dict) -> List[dict]:
        """解析 FinancialDataClient V2 协议返回"""
        if not raw or not isinstance(raw, dict):
            return []
        results = raw.get('results', [])
        if results and isinstance(results, list) and isinstance(results[0], dict):
            fields = results[0].get('meta', {}).get('fields', [])
            data_rows = results[0].get('data', [])
            if fields and data_rows:
                return [dict(zip(fields, row)) for row in data_rows]
        items = raw.get('data', raw.get('items', []))
        if isinstance(items, list):
            return [i for i in items if isinstance(i, dict)]
        return []

    def collect_market_context(self, date: str) -> Dict[str, Any]:
        """采集市场话题素材：大盘指数 + 宏观数据 + 宏观事件 + 热门新闻"""
        result = {
            'index_snapshot': {},
            'macro_dashboard': None,
            'macro_events': [],
            'hot_news': [],
        }

        try:
            def _fetch_indices():
                from quant import batch_market_snapshot
                indices = ['000001.SH', '399001.SZ', '399006.SZ']
                snap = batch_market_snapshot(indices)
                idx = {}
                name_map = {'SH.000001': '上证指数', 'SZ.399001': '深证成指', 'SZ.399006': '创业板指'}
                if snap:
                    for code, data in snap.items():
                        name = name_map.get(code, data.get('name', code))
                        last = data.get('last_price', 0) or 0
                        prev = data.get('prev_close_price', 0) or 0
                        change_rate = round((last - prev) / prev * 100, 2) if prev else 0
                        idx[name] = {
                            'last_price': last,
                            'change_rate': change_rate,
                            'volume': data.get('volume'),
                            'turnover': data.get('turnover'),
                        }
                return idx

            result['index_snapshot'] = _run_with_timeout(_fetch_indices, timeout=10, default={}) or {}
        except Exception as e:
            logger.warning(f"[ContentCollector] 大盘指数获取失败: {e}")

        try:
            def _fetch_dashboard():
                from service.storage.database_manager import db_manager
                rows = db_manager.execute_query(
                    """SELECT macro_symbol, date, value FROM macro_data
                       WHERE date = (SELECT MAX(date) FROM macro_data)"""
                )
                if rows:
                    return {
                        'summary': f"最新宏观数据日期: {rows[0]['date']}，共{len(rows)}项指标",
                        'indicators': {r['macro_symbol']: r['value'] for r in rows},
                    }
                return None

            dash = _run_with_timeout(_fetch_dashboard, timeout=10)
            if dash:
                result['macro_dashboard'] = dash
        except Exception as e:
            logger.warning(f"[ContentCollector] 宏观仪表盘获取失败: {e}")

        try:
            def _fetch_macro_events():
                from service.monitor.event_service import event_service
                return event_service.query_events(event_date=date, level='macro', limit=20)

            events = _run_with_timeout(_fetch_macro_events, timeout=_STEP_TIMEOUT, default=[])
            result['macro_events'] = [{
                'category': e.get('category'),
                'severity': e.get('severity'),
                'title': e.get('title'),
                'description': e.get('description'),
                'metrics': e.get('metrics', {}),
            } for e in (events or [])]
        except Exception as e:
            logger.warning(f"[ContentCollector] 宏观事件获取失败: {e}")

        try:
            def _fetch_news():
                from service.datapip.financial_data_client import FinancialDataClient
                client = FinancialDataClient()
                return client.get_news_search('A股市场今日热点', limit=10)

            news = _run_with_timeout(_fetch_news, timeout=_STEP_TIMEOUT)
            if news and isinstance(news, dict):
                items = news.get('results', news.get('data', news.get('items', [])))
                if isinstance(items, list):
                    result['hot_news'] = [{
                        'title': n.get('title', ''),
                        'summary': (n.get('abstractExtract') or n.get('doc') or n.get('content') or n.get('summary', ''))[:200],
                        'source': n.get('siteName', n.get('source', '')),
                    } for n in items[:10] if isinstance(n, dict) and n.get('title')]
        except Exception as e:
            logger.warning(f"[ContentCollector] 热门新闻获取失败: {e}")

        return result

    def collect_enriched_sector_context(self, date: str) -> Dict[str, Any]:
        """采集增强版行业素材：Top5热门板块(含资金流) + 板块池分析摘要 + 轮动上下文 + 事件
        + 妙想实时板块行情（股价聚合）+ 妙想当日新闻（含日期校验）"""
        result = {
            'hot_plates_top5': [],
            'sector_pool_analyses': [],
            'sector_rotation_context': '',
            'sector_events': [],
            'mx_sector_performance': [],   # 妙想: 申万行业涨跌幅实时聚合
            'mx_sector_news': [],          # 妙想: 当日板块新闻（日期已校验）
        }

        # ── 妙想: 实时板块行情（聚合今日涨幅前200股 → 申万一级行业排名）──
        try:
            def _fetch_mx_sector_perf():
                from service.datapip.miaoxiang_client import MiaoXiangClient
                mx = MiaoXiangClient()
                return mx.get_sector_performance(top_n=15)

            perf = _run_with_timeout(_fetch_mx_sector_perf, timeout=20, default=[])
            result['mx_sector_performance'] = perf or []
            if perf:
                logger.info(f"[ContentCollector] 妙想板块行情: Top3={[p['sector'] for p in perf[:3]]}")
        except Exception as e:
            logger.warning(f"[ContentCollector] 妙想板块行情获取失败: {e}")

        # ── 妙想: 当日板块新闻（日期校验确保是今日数据）──
        try:
            def _fetch_mx_sector_news():
                from service.datapip.miaoxiang_client import MiaoXiangClient
                mx = MiaoXiangClient()
                return mx.get_sector_news_today()

            news = _run_with_timeout(_fetch_mx_sector_news, timeout=20, default=[])
            result['mx_sector_news'] = news or []
            today_count = len(result['mx_sector_news'])
            logger.info(f"[ContentCollector] 妙想板块新闻: 当日 {today_count} 条")
            if today_count == 0:
                logger.warning("[ContentCollector] 妙想板块新闻: 未获取到当日数据，可能非交易日")
        except Exception as e:
            logger.warning(f"[ContentCollector] 妙想板块新闻获取失败: {e}")

        try:
            from service.datapip.financial_data_client import FinancialDataClient
            client = FinancialDataClient()
        except Exception as e:
            logger.warning(f"[ContentCollector] FinancialDataClient 初始化失败: {e}")
            return result

        gainers = []
        losers = []
        try:
            def _fetch_ranking():
                raw_gain = client.get_hot_plates(count=10, rank_field='changePercent') or {}
                raw_lose = client.get_hot_plates(count=10, rank_field='changePercent', reversed_order=True) or {}
                g_list, l_list = [], []
                for src, out in [(raw_gain, g_list), (raw_lose, l_list)]:
                    items = self._parse_v2_results(src)
                    for item in items:
                        main_inflow = item.get('mainInflow')
                        capital_flow = None
                        if main_inflow is not None:
                            try:
                                v = float(main_inflow)
                                if abs(v) >= 1e8:
                                    capital_flow = {'main_net_inflow': round(v / 1e8, 2), 'unit': '亿'}
                                else:
                                    capital_flow = {'main_net_inflow': round(v / 1e4, 0), 'unit': '万'}
                            except (TypeError, ValueError):
                                pass
                        out.append({
                            'name': item.get('name', ''),
                            'symbol': item.get('symbol', ''),
                            'change_pct': item.get('changePercent'),
                            'capital_flow': capital_flow,
                        })
                return g_list, l_list

            fetched = _run_with_timeout(_fetch_ranking, timeout=15)
            if fetched:
                gainers, losers = fetched
        except Exception as e:
            logger.warning(f"[ContentCollector] 板块排行获取失败: {e}")

        result['hot_plates_top5'] = gainers[:5]

        if result['hot_plates_top5']:
            try:
                def _fetch_turnover():
                    for p in result['hot_plates_top5']:
                        sym = p.get('symbol')
                        if not sym:
                            continue
                        try:
                            snap = client.get_snapshot(sym)
                            items = self._parse_v2_results(snap)
                            if items:
                                amount = items[0].get('amount')
                                if amount is not None:
                                    try:
                                        v = float(amount)
                                        if v >= 1e8:
                                            p['turnover'] = f"{round(v / 1e8, 1)}亿"
                                        else:
                                            p['turnover'] = f"{round(v / 1e4, 0)}万"
                                    except (TypeError, ValueError):
                                        pass
                        except Exception:
                            pass

                _run_with_timeout(_fetch_turnover, timeout=15)
            except Exception as e:
                logger.warning(f"[ContentCollector] 成交额补查失败: {e}")

        gain_names = [p['name'] for p in gainers[:5] if p.get('name')]
        lose_names = [p['name'] for p in losers[:5] if p.get('name')]
        if gain_names or lose_names:
            parts = []
            if gain_names:
                parts.append(f"资金流入方向: {', '.join(gain_names)}")
            if lose_names:
                parts.append(f"资金流出方向: {', '.join(lose_names)}")
            result['sector_rotation_context'] = '；'.join(parts)

        try:
            def _fetch_pool_analyses():
                from service.storage.database_manager import db_manager
                pool_rows = db_manager.execute_query(
                    "SELECT sector_key, name FROM sector_pool ORDER BY sort_order, id"
                )
                if not pool_rows:
                    return []
                analyses = []
                for r in pool_rows:
                    key = r['sector_key']
                    hist = db_manager.execute_query(
                        """SELECT sector_name, direction, confidence, summary, generated_at
                           FROM sector_analysis_history
                           WHERE sector_key = ?
                           ORDER BY generated_at DESC LIMIT 1""",
                        (key,)
                    )
                    entry = {'sector_key': key, 'sector_name': r['name']}
                    if hist:
                        h = hist[0]
                        entry.update({
                            'direction': h['direction'],
                            'confidence': h['confidence'],
                            'summary': h['summary'],
                            'generated_at': h['generated_at'],
                        })
                    analyses.append(entry)
                return analyses

            result['sector_pool_analyses'] = _run_with_timeout(_fetch_pool_analyses, timeout=10, default=[]) or []
        except Exception as e:
            logger.warning(f"[ContentCollector] 板块池分析摘要获取失败: {e}")

        try:
            def _fetch_sector_events():
                from service.monitor.event_service import event_service
                return event_service.query_events(event_date=date, level='sector', limit=20)

            events = _run_with_timeout(_fetch_sector_events, timeout=_STEP_TIMEOUT, default=[])
            result['sector_events'] = [{
                'category': e.get('category'),
                'severity': e.get('severity'),
                'title': e.get('title'),
                'description': e.get('description'),
                'symbol_name': e.get('symbol_name'),
                'metrics': e.get('metrics', {}),
            } for e in (events or [])]
        except Exception as e:
            logger.warning(f"[ContentCollector] 板块事件获取失败: {e}")

        return result

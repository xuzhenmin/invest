"""事实核验流水线 — 提取声明 → 获取真实数据 → 对比判断"""

import os
import json
import logging
import requests
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class FactChecker:

    def __init__(self):
        self._api_key = os.getenv('DEEPSEEK_API_KEY')

    def verify(self, xhs_title: str, xhs_body: str, xhs_tags: list) -> Dict[str, Any]:
        """主入口：两步流水线"""
        content_text = f"标题: {xhs_title}\n正文: {xhs_body}\n标签: {', '.join(xhs_tags or [])}"

        claims = self._extract_claims(content_text)
        if not claims:
            return {'overall_score': 100, 'reason': '未发现可核验的具体数据声明', 'verdicts': []}

        logger.info(f"[FactChecker] 提取到 {len(claims)} 条声明，开始并行核验")

        real_data = {}
        fetchers = {
            'stock': self._fetch_stock_snapshot,
            'sector': self._fetch_sector_analysis,
            'diagnosis': self._fetch_diagnosis_report,
            'capital': self._fetch_capital_flow,
            'events': self._fetch_stock_events,
        }

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {name: executor.submit(fn, claims) for name, fn in fetchers.items()}
            failures = []
            for name, future in futures.items():
                try:
                    data, errs = future.result(timeout=60)
                    real_data[name] = data
                    failures.extend(errs)
                except Exception as e:
                    logger.warning(f"[FactChecker] {name} 数据获取失败: {e}")
                    real_data[name] = {}
                    failures.append(f"{name}: {str(e)}")

        result = self._judge_claims(content_text, claims, real_data, failures)
        return result

    def _extract_claims(self, content_text: str) -> List[Dict]:
        prompt = f"""请从以下小红书财经内容中，提取所有可核验的具体数据声明。

【内容】
{content_text}

请严格返回以下JSON格式:
{{
  "claims": [
    {{
      "type": "stock_performance|sector_performance|macro_data|market_breadth|capital_flow",
      "subject": "主体名称（股票名/板块名/指数名）",
      "symbol": "证券代码（如已知，格式如600519.SH、000001.SZ）",
      "claim": "具体声明（如：茅台今日涨幅+3.5%）",
      "value": "声明中的具体数值（如：+3.5%、2.3亿、1200点）",
      "context": "声明的上下文"
    }}
  ]
}}

注意:
1. 只提取有具体数值的声明，不提取模糊描述
2. 最多提取5条最关键的声明
3. 如果没有可核验的具体数值，返回 {{"claims": []}}"""

        try:
            result = self._call_deepseek(prompt, "你是一个专业的财经内容核验员。请严格返回JSON。",
                                         temperature=0.1, max_tokens=2000)
            if isinstance(result, dict) and 'claims' in result:
                return result['claims']
            return []
        except Exception as e:
            logger.error(f"[FactChecker] 提取声明失败: {e}")
            return []

    def _fetch_stock_snapshot(self, claims: List[Dict]) -> tuple:
        data = {}
        failures = []
        stock_claims = [c for c in claims if c.get('type') == 'stock_performance' and c.get('symbol')]
        if not stock_claims:
            return data, failures

        symbols = list({c['symbol'] for c in stock_claims})
        try:
            from quant import batch_market_snapshot
            snap = batch_market_snapshot(symbols)
            if snap:
                for sym, info in snap.items():
                    data[sym] = {
                        'last_price': info.get('last_price'),
                        'change_rate': info.get('change_rate'),
                        'turnover': info.get('turnover'),
                        'volume': info.get('volume'),
                        'source': 'market_snapshot',
                    }
        except Exception as e:
            logger.warning(f"[FactChecker] batch_market_snapshot 失败: {e}")
            try:
                from service.datapip.financial_data_client import FinancialDataClient
                client = FinancialDataClient()
                for sym in symbols:
                    try:
                        snap = client.get_snapshot(sym)
                        if snap:
                            items = snap.get('data', snap.get('items', []))
                            if items and isinstance(items, list) and items:
                                info = items[0] if isinstance(items[0], dict) else {}
                            else:
                                info = snap if isinstance(snap, dict) else {}
                            data[sym] = {
                                'last_price': info.get('lastPrice', info.get('last_price')),
                                'change_rate': info.get('changePercent', info.get('change_rate')),
                                'source': 'financial_client',
                            }
                    except Exception:
                        pass
            except Exception as e2:
                failures.append(f"stock_snapshot: {str(e2)}")

        return data, failures

    def _fetch_sector_analysis(self, claims: List[Dict]) -> tuple:
        data = {}
        failures = []
        sector_claims = [c for c in claims if c.get('type') == 'sector_performance' and c.get('subject')]
        if not sector_claims:
            return data, failures

        try:
            from service.storage.database_manager import db_manager
            for c in sector_claims:
                sector_name = c['subject']
                rows = db_manager.execute_query(
                    """SELECT direction, confidence, summary, price_data, generated_at
                       FROM sector_analysis_history
                       WHERE sector_name LIKE ?
                       ORDER BY generated_at DESC LIMIT 1""",
                    (f'%{sector_name}%',)
                )
                if rows:
                    r = rows[0]
                    data[sector_name] = {
                        'direction': r['direction'],
                        'confidence': r['confidence'],
                        'summary': r['summary'],
                        'generated_at': r['generated_at'],
                        'source': 'sector_analysis_history',
                    }
        except Exception as e:
            logger.warning(f"[FactChecker] 板块历史分析查询失败: {e}")
            failures.append(f"sector_analysis: {str(e)}")

        return data, failures

    def _fetch_diagnosis_report(self, claims: List[Dict]) -> tuple:
        data = {}
        failures = []
        stock_claims = [c for c in claims if c.get('type') == 'stock_performance' and c.get('symbol')]
        if not stock_claims:
            return data, failures

        symbols = list({c['symbol'] for c in stock_claims})
        try:
            from service.storage.query_service import query_service
            batch = query_service.get_latest_diagnoses_batch(symbols)
            if batch and isinstance(batch, dict):
                for sym, diag in batch.items():
                    if diag:
                        data[sym] = {
                            'health_score': diag.get('health_score'),
                            'summary': diag.get('summary') or diag.get('conclusion'),
                            'source': 'diagnosis_report',
                        }
        except Exception as e:
            logger.debug(f"[FactChecker] 诊断报告查询失败（忽略）: {e}")

        return data, failures

    def _fetch_capital_flow(self, claims: List[Dict]) -> tuple:
        data = {}
        failures = []
        capital_claims = [c for c in claims if c.get('type') == 'capital_flow' and c.get('symbol')]
        if not capital_claims:
            return data, failures

        symbols = list({c['symbol'] for c in capital_claims})
        try:
            from service.datapip.financial_data_client import FinancialDataClient
            client = FinancialDataClient()
            for sym in symbols:
                try:
                    flow = client.get_capital_flow(sym)
                    if flow:
                        items = flow.get('data', flow.get('items', []))
                        if isinstance(items, list) and items:
                            info = items[0] if isinstance(items[0], dict) else {}
                        else:
                            info = flow if isinstance(flow, dict) else {}
                        data[sym] = {
                            'main_net_inflow': info.get('mainNetInflow', info.get('main_net_inflow')),
                            'source': 'financial_client',
                        }
                except Exception:
                    pass
        except Exception as e:
            try:
                from service.storage.query_service import query_service
                for sym in symbols:
                    try:
                        cf = query_service.get_capital_flow(sym)
                        if cf:
                            data[sym] = {**cf, 'source': 'query_service'}
                    except Exception:
                        pass
            except Exception as e2:
                failures.append(f"capital_flow: {str(e2)}")

        return data, failures

    def _fetch_stock_events(self, claims: List[Dict]) -> tuple:
        data = {}
        failures = []
        stock_claims = [c for c in claims if c.get('symbol')]
        if not stock_claims:
            return data, failures

        symbols = list({c['symbol'] for c in stock_claims})
        try:
            from service.monitor.event_service import event_service
            for sym in symbols:
                try:
                    events = event_service.query_events(symbol=sym, limit=5)
                    if events:
                        data[sym] = [{
                            'title': e.get('title', ''),
                            'description': e.get('description', ''),
                            'severity': e.get('severity', ''),
                        } for e in events]
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"[FactChecker] 个股事件查询失败（忽略）: {e}")
            failures.append(f"stock_events: {str(e)}")

        return data, failures

    def _judge_claims(self, content_text: str, claims: List[Dict],
                      real_data: Dict, failures: List[str]) -> Dict[str, Any]:
        data_summary = json.dumps({
            'claims': claims,
            'real_data': real_data,
        }, ensure_ascii=False, default=str)

        failures_text = f"\n注：以下数据源获取失败，相关声明视为无法核验: {failures}" if failures else ""

        prompt = f"""请对以下财经内容中的具体数据声明进行事实核验，对比提供的真实数据给出核验结论。

【原始内容摘要】
{content_text[:500]}

【待核验声明 + 真实数据对比】
{data_summary}
{failures_text}

请严格返回以下JSON格式:
{{
  "overall_score": 85,
  "verdicts": [
    {{
      "claim": "原始声明",
      "verdict": "pass|fail|unverifiable",
      "real_value": "真实数据中的对应值",
      "deviation": "与声明的偏差描述",
      "comment": "简短说明"
    }}
  ],
  "summary": "整体核验结论摘要（2-3句）"
}}

评分规则:
- overall_score: 0-100分，100=完全准确，0=严重失实
- pass: 数据与声明基本一致（误差<5%）
- fail: 数据与声明明显不符
- unverifiable: 无对应真实数据，无法判断
- 如果所有声明均为unverifiable（数据源不可用），overall_score给85，说明数据源不可用"""

        try:
            result = self._call_deepseek(prompt, "你是一个专业的财经内容审核员，专注于数据准确性核验。请严格返回JSON。",
                                         temperature=0.1, max_tokens=3000)
            if isinstance(result, dict) and 'overall_score' in result:
                return result
            return {'overall_score': 80, 'reason': '核验完成', 'verdicts': [], 'raw': result}
        except Exception as e:
            logger.error(f"[FactChecker] 判断声明失败: {e}")
            return {'overall_score': None, 'error': str(e), 'verdicts': []}

    def _call_deepseek(self, prompt: str, system_message: str,
                       temperature: float = 0.1, max_tokens: int = 3000) -> dict:
        if not self._api_key:
            raise Exception("未配置 DEEPSEEK_API_KEY")

        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }

        response = requests.post(
            'https://api.deepseek.com/v1/chat/completions',
            headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {self._api_key}'},
            json=payload, timeout=60,
        )

        if response.status_code != 200:
            raise Exception(f"DeepSeek API 错误: {response.status_code} {response.text[:200]}")

        result = response.json()
        content = result['choices'][0]['message'].get('content') or ''
        if not content.strip():
            raise Exception("DeepSeek 返回内容为空")
        return json.loads(content)

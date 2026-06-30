"""内容运营核心业务 — 素材生成 + 多平台格式转写 + 事实核验"""

import os
import json
import logging
import requests
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, Any, Optional

from .data_collector import ContentDataCollector

logger = logging.getLogger(__name__)


class ContentOpsService:

    GOAL_STRATEGIES = {
        'follow': """【运营目标：涨粉关注】
- 标题要有人设感，像一个你想关注的人会说的话
- 正文开头用固定的招牌语或口头禅，建立辨识度
- 至少包含一个"未完待续"式钩子
- 结尾互动引导：用"关注我，明天继续聊"或"关注不迷路，每天一条财经日记"等自然的关注引导
- 语气要像一个你在小红书上会想关注的朋友：懂行但不端着，有态度但不偏激
- 整体传达：跟着这个号看，每天花1分钟就能跟上市场""",

        'like_collect': """【运营目标：点赞收藏】
- 标题要有"干货预警"感
- 正文要有强结构化输出：用"划重点""一句话总结""3个关键词"等形式，信息密度拉满
- knowledge_seed 部分包装成"一个你早该知道的概念"，带上记忆口诀
- 结尾互动引导：用"觉得有用就点个收藏吧，下次看盘翻出来对照着看"等自然的收藏引导
- 整体让读者觉得：这条信息密度高，存下来以后用得上""",

        'discuss': """【运营目标：引发讨论】
- 标题要制造争议或悬念
- 正文要大胆抛出一个有争议但有理有据的个人观点，用"我的看法是..."或"说个可能不讨喜的话..."引入
- 正文中至少2个互动触发点：一个是反问，一个是二选一问题
- 结尾必须用一个让人忍不住回答的开放问题
- 话题标签加入讨论类标签（如 #你怎么看 #今日讨论 #评论区见）
- 整体让读者觉得：这个观点有意思但我不完全同意，我得说两句""",
    }

    def __init__(self):
        self._api_key = os.getenv('DEEPSEEK_API_KEY')
        self._collector = ContentDataCollector()
        self._ensure_schema()

    # ── 公开方法 ──

    def verify_content(self, content_id: int) -> Dict[str, Any]:
        """阶段3: 对已转写的内容进行事实核验"""
        from service.storage.database_manager import db_manager

        row = db_manager.execute_query(
            "SELECT * FROM xhs_content WHERE id = ?", (content_id,)
        )
        if not row:
            raise ValueError(f"内容不存在: id={content_id}")
        record = row[0]

        if not record.get('xhs_body'):
            raise ValueError("内容尚未转写，请先执行转写")

        tags = json.loads(record['xhs_tags']) if record.get('xhs_tags') else []

        from .fact_checker import FactChecker
        checker = FactChecker()
        result = checker.verify(
            xhs_title=record['xhs_title'],
            xhs_body=record['xhs_body'],
            xhs_tags=tags,
        )

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db_manager.execute_update(
            """UPDATE xhs_content
               SET verification_result=?, verified_at=?, updated_at=?
               WHERE id=?""",
            (json.dumps(result, ensure_ascii=False, default=str), now, now, content_id)
        )

        logger.info(f"[ContentOps] 内容验证完成, id={content_id}, score={result.get('overall_score')}")
        return {'id': content_id, 'verification_result': result, 'verified_at': now}

    def generate_material(self) -> Dict[str, Any]:
        """阶段1: 采集数据 → 5路并行调用 DeepSeek 生成结构化素材"""
        today = datetime.now().strftime('%Y-%m-%d')
        logger.info(f"[ContentOps] 开始生成素材: {today}")

        logger.info("[ContentOps] 步骤1/3: 采集市场数据...")
        market = self._collector.collect_market_context(today)
        logger.info("[ContentOps] 步骤2/3: 采集行业数据...")
        sector = self._collector.collect_enriched_sector_context(today)

        prev_mentions = self._get_previous_mentions()

        logger.info("[ContentOps] 步骤3/3: 5路并行生成素材...")
        gen_map = {
            'market_overview': (self._gen_market_overview, (market, today)),
            'hot_boards': (self._gen_hot_boards, (market, sector, today)),
            'hot_topics': (self._gen_hot_topics, (market, sector, today)),
            'knowledge_seed': (self._gen_knowledge_seed, (market, sector, today)),
            'sector_review': (self._gen_sector_review, (prev_mentions, sector, today)),
        }

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {name: executor.submit(fn, *args) for name, (fn, args) in gen_map.items()}
            raw_material = {}
            for name, future in futures.items():
                try:
                    raw_material[name] = future.result(timeout=120)
                except Exception as e:
                    logger.error(f"[ContentOps] {name} 生成失败: {e}")
                    raw_material[name] = None

        failed = [k for k, v in raw_material.items() if v is None]
        if failed:
            for name in failed:
                fn, args = gen_map[name]
                try:
                    raw_material[name] = fn(*args)
                except Exception as e:
                    logger.error(f"[ContentOps] {name} 重试仍失败: {e}")

        core_keys = ['market_overview', 'hot_boards', 'hot_topics']
        if all(raw_material.get(k) is None for k in core_keys):
            raise Exception("素材生成失败：核心模块全部为空，请检查 DEEPSEEK_API_KEY 配置")

        content_id = self._save_content(today, 'raw', raw_material)
        self._save_sector_mentions(content_id, today, raw_material.get('hot_boards', []),
                                   sector.get('hot_plates_top5', []))
        raw_material['id'] = content_id
        raw_material['content_date'] = today
        logger.info(f"[ContentOps] 素材生成完成, id={content_id}")
        return raw_material

    def format_content(self, content_id: int, platform: str = 'note',
                       user_instructions: str = None, goal: str = None,
                       modules: list = None) -> Dict[str, Any]:
        """阶段2: 将素材转写为指定平台的合规内容"""
        from service.storage.database_manager import db_manager

        row = db_manager.execute_query(
            "SELECT * FROM xhs_content WHERE id = ?", (content_id,)
        )
        if not row:
            raise ValueError(f"内容不存在: id={content_id}")
        record = row[0]

        raw = record.get('raw_material')
        if not raw:
            raise ValueError("素材数据为空，请先生成素材")
        raw_material = json.loads(raw) if isinstance(raw, str) else raw

        formatted = self._format_for_platform(raw_material, platform, user_instructions, goal, modules)

        db_manager.execute_update(
            """UPDATE xhs_content
               SET stage='formatted', xhs_title=?, xhs_body=?, xhs_tags=?,
                   xhs_cover_text=?, updated_at=?
               WHERE id=?""",
            (formatted['title'], formatted['body'],
             json.dumps(formatted['tags'], ensure_ascii=False),
             formatted['cover_text'],
             datetime.now().strftime('%Y-%m-%d %H:%M:%S'), content_id)
        )

        return {
            'id': content_id,
            'title': formatted['title'],
            'body': formatted['body'],
            'tags': formatted['tags'],
            'cover_text': formatted['cover_text'],
        }

    def get_content_list(self, limit: int = 20) -> list:
        from service.storage.database_manager import db_manager
        rows = db_manager.execute_query(
            "SELECT * FROM xhs_content ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        result = []
        for r in rows:
            item = dict(r)
            for field in ('raw_material', 'xhs_tags', 'verification_result'):
                if item.get(field):
                    try:
                        item[field] = json.loads(item[field])
                    except (json.JSONDecodeError, TypeError):
                        pass
            result.append(item)
        return result

    def get_content_detail(self, content_id: int) -> Optional[Dict]:
        from service.storage.database_manager import db_manager
        rows = db_manager.execute_query(
            "SELECT * FROM xhs_content WHERE id = ?", (content_id,)
        )
        if not rows:
            return None
        record = dict(rows[0])
        for field in ('raw_material', 'xhs_tags', 'verification_result'):
            if record.get(field):
                try:
                    record[field] = json.loads(record[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        return record

    def delete_content(self, content_id: int) -> bool:
        from service.storage.database_manager import db_manager
        affected = db_manager.execute_update(
            "DELETE FROM xhs_content WHERE id = ?", (content_id,)
        )
        return affected > 0

    # ── 阶段1: 5路独立素材生成 ──

    def _gen_market_overview(self, market: dict, date: str) -> dict:
        data_summary = json.dumps({
            'date': date,
            'indices': market.get('index_snapshot', {}),
            'macro_dashboard': market.get('macro_dashboard'),
            'macro_events': market.get('macro_events', [])[:10],
            'hot_news': market.get('hot_news', [])[:8],
        }, ensure_ascii=False, default=str)

        prompt = f"""请基于以下{date}的市场数据，输出市场总览素材。

【数据汇总】
{data_summary}

请严格返回以下JSON格式:
{{
  "summary": "今日大盘一句话概括（包含涨跌方向和幅度）",
  "key_indices": {{"上证指数": "+0.5%", "深证成指": "-0.3%", "创业板指": "+1.2%"}},
  "mood": "热闹/冷清/分化/纠结/躁动",
  "notable_phenomena": ["值得关注的市场现象1", "现象2"]
}}

要求:
1. summary 必须包含大盘指数的实际涨跌幅数据
2. key_indices 使用提供的实际数据
3. mood 根据成交量、涨跌分布、热点集中度综合判断
4. notable_phenomena 提取2-3个最值得关注的市场现象"""

        system = (
            "你是一个专业的市场研究员，负责输出客观、全面的市场总览。"
            "请基于提供的原始数据做分析，数据要具体精确。请严格返回JSON。"
        )
        return self._call_deepseek(prompt, system, temperature=0.5, max_tokens=3000)

    def _gen_hot_boards(self, market: dict, sector: dict, date: str) -> list:
        # 当日板块新闻（已校验为今日数据，是识别具体热点板块最准的来源）
        mx_news = sector.get('mx_sector_news', [])
        news_block = ''
        if mx_news:
            snippets = []
            for n in mx_news[:8]:
                snippets.append(
                    f"[{n['source']} {n['date'][:16]}] {n['title']}\n{n['content'][:300]}"
                )
            news_block = '\n\n'.join(snippets)

        # 申万行业实时涨跌幅（基于股价聚合，用于补充大行业方向参考）
        mx_perf = sector.get('mx_sector_performance', [])
        perf_block = ''
        if mx_perf:
            lines = [f"{p['sector']} 平均涨幅{p['avg_change_pct']:+.2f}% ({p['stock_count']}只)"
                     for p in mx_perf[:8]]
            perf_block = '\n'.join(lines)

        prompt = f"""你是一个专业的板块分析师。请基于以下{date}的真实数据，识别并分析今日A股市场中最热门的5个**概念/主题板块**（如WiFi6、MiniLED、CPO、半导体、玻璃基板等具体板块，不是宽泛行业分类）。

【今日板块行情新闻】（已校验为{date}当日数据，是主要依据）
{news_block or '暂无当日新闻'}

【申万行业涨跌参考】（辅助背景，按平均涨幅前列）
{perf_block or '暂无数据'}

请严格返回JSON数组（5个元素）:
[
  {{
    "sector_name": "具体板块名称（如WiFi6、MiniLED概念、CPO概念等）",
    "change_pct": "今日涨幅（从新闻中提取真实数据，如+6.12%）",
    "turnover": "成交额（从新闻提取，无则填null）",
    "capital_flow": "资金流向描述（有数据则填，无则填null）",
    "driver": "板块上涨驱动因素（2-3句，结合新闻事件和产业逻辑）",
    "rotation_context": "该板块在今日市场轮动中的位置（领涨/跟涨/补涨/分歧等）",
    "related_stocks": ["代表性个股和涨幅，从新闻中提取"],
    "life_connection": "这个板块和普通人日常生活或消费的关联",
    "pool_analysis": null
  }}
]

要求：
1. 选取今日真正活跃的**具体概念/主题板块**，不要选"电子"、"计算机"等申万一级行业
2. change_pct 必须从新闻中提取真实数据，不可编造
3. related_stocks 从新闻中提取今日该板块领涨个股和具体涨幅
4. 直接返回JSON数组，不要包裹在对象中"""

        system = "你是专业板块分析师，从新闻中提取今日热点板块并做深度分析。请严格返回JSON数组。"
        result = self._call_deepseek(prompt, system, temperature=0.4, max_tokens=4000)
        if isinstance(result, dict) and 'sectors' in result:
            raw_boards = result['sectors']
        elif isinstance(result, dict) and 'boards' in result:
            raw_boards = result['boards']
        elif isinstance(result, list):
            raw_boards = result
        else:
            raw_boards = []

        return self._enrich_and_dedup_boards(raw_boards)

    def _enrich_and_dedup_boards(self, boards: list) -> list:
        """去重 + 对 change_pct 为空/非数字的板块补全真实行情
        优先用 Futu 官方板块代码查快照，fallback 到 MiaoXiang 成分股均值"""
        import re

        def _normalize_name(name: str) -> str:
            name = name or ''
            name = re.sub(r'[\(（][^)\）]*[\)）]', '', name)
            name = name.replace('板块', '').replace('概念', '').replace(' ', '').strip()
            return name.upper()

        def _is_real_pct(v) -> bool:
            if not v or str(v).lower() in ('null', 'none', 'n/a', ''):
                return False
            return bool(re.match(r'^[+-]?\d+\.?\d*%?$', str(v).strip()))

        # 去重：按规范化名称保留第一个
        seen, deduped = set(), []
        for b in boards:
            key = _normalize_name(b.get('sector_name', ''))
            if key and key not in seen:
                seen.add(key)
                deduped.append(b)

        need_enrich = [b for b in deduped if not _is_real_pct(b.get('change_pct'))]

        # ── Step 1: Futu 官方板块代码 → 快照（用于所有板块，Futu 收盘数据更权威）──
        futu_snapshot = {}
        try:
            from quant import get_concept_board_snapshot
            # 所有板块都查 Futu（覆盖 DeepSeek 可能提取的中午数据）
            all_names = [b.get('sector_name', '') for b in deduped]
            futu_snapshot = get_concept_board_snapshot(all_names) or {}
            logger.info(f"[ContentOps] Futu板块快照命中: {list(futu_snapshot.keys())}")
        except Exception as e:
            logger.warning(f"[ContentOps] Futu板块快照查询失败: {e}")

        for b in deduped:
            name = b.get('sector_name', '')
            snap = futu_snapshot.get(name)
            if not snap:
                continue
            chg = snap.get('change_pct')
            if chg is not None:
                b['change_pct'] = f"{chg:+.2f}%"
            turnover = snap.get('turnover')
            if turnover and not b.get('turnover'):
                if turnover >= 1e8:
                    b['turnover'] = f"{round(turnover / 1e8, 1)}亿"
                else:
                    b['turnover'] = f"{round(turnover / 1e4, 0):.0f}万"
            rc = snap.get('raise_count')
            fc = snap.get('fall_count')
            if rc is not None and fc is not None and not b.get('rotation_context'):
                b['rotation_context'] = f"{rc}涨{fc}跌"

        # ── Step 2: Futu 未命中且仍缺 change_pct 的 → MiaoXiang 成分股均值（fallback）──
        still_need = [b for b in deduped
                      if b.get('sector_name', '') not in futu_snapshot
                      and not _is_real_pct(b.get('change_pct'))]
        if still_need:
            try:
                from service.datapip.miaoxiang_client import MiaoXiangClient

                def _safe_chg(v):
                    try:
                        return float(v) if v not in (None, '', 'N/A') else 0.0
                    except (TypeError, ValueError):
                        return 0.0

                for b in still_need:
                    name = b.get('sector_name', '')
                    try:
                        mx = MiaoXiangClient()
                        stocks = mx.select_stocks(f"今日{name}的股票")
                        if not stocks:
                            continue
                        normalized = []
                        for s in stocks:
                            if s and isinstance(s, dict):
                                try:
                                    normalized.append(mx.normalize_stock_record(s))
                                except Exception:
                                    pass
                        changes = [_safe_chg(s.get('change_pct')) for s in normalized if s]
                        changes = [c for c in changes if c != 0.0]
                        if changes:
                            avg = round(sum(changes) / len(changes), 2)
                            b['change_pct'] = f"{avg:+.2f}%"
                        if not b.get('related_stocks'):
                            top = sorted(
                                [s for s in normalized if s],
                                key=lambda s: _safe_chg(s.get('change_pct')),
                                reverse=True
                            )[:5]
                            b['related_stocks'] = [
                                f"{s['name']}({s.get('change_pct', '')}%)"
                                for s in top if s and s.get('name')
                            ]
                    except Exception as e:
                        logger.warning(f"[ContentOps] MiaoXiang板块补查失败 {name}: {e}")
            except Exception as e:
                logger.warning(f"[ContentOps] MiaoXiang fallback失败: {e}")

        return deduped

    def _gen_hot_topics(self, market: dict, sector: dict, date: str) -> list:
        data_summary = json.dumps({
            'date': date,
            'hot_news': market.get('hot_news', [])[:8],
            'macro_events': market.get('macro_events', [])[:10],
            'sector_events': sector.get('sector_events', [])[:10],
        }, ensure_ascii=False, default=str)

        prompt = f"""请基于以下{date}的新闻和事件数据，提炼2-3个最有讨论价值的热点话题。

【数据汇总】
{data_summary}

请严格返回以下JSON格式（数组，2-3个元素）:
{{
  "topics": [
    {{
      "title": "话题标题",
      "source": "新闻/事件来源",
      "summary": "事件概要（2-3句）",
      "market_impact": "对市场的影响分析",
      "life_angle": "普通人视角怎么看这件事"
    }}
  ]
}}

要求:
1. 优先选择有实质性市场影响的话题
2. 话题之间不要重复，覆盖不同领域（如政策、行业、国际等）
3. life_angle 要贴近普通人的日常感知"""

        system = (
            "你是一个专业的财经话题策划师，擅长从海量信息中找到最有讨论价值的话题。请严格返回JSON。"
        )
        result = self._call_deepseek(prompt, system, temperature=0.5, max_tokens=2000)
        if isinstance(result, dict) and 'topics' in result:
            return result['topics']
        if isinstance(result, list):
            return result
        return [result] if result else []

    def _gen_knowledge_seed(self, market: dict, sector: dict, date: str) -> dict:
        context_summary = json.dumps({
            'date': date,
            'market_mood': market.get('index_snapshot', {}),
            'hot_plates': [p.get('name', '') for p in sector.get('hot_plates_top5', [])[:3]],
            'macro_events_titles': [e.get('title', '') for e in market.get('macro_events', [])[:5]],
        }, ensure_ascii=False, default=str)

        prompt = f"""请基于以下{date}的市场概况，选择一个与今日市场相关的专业概念进行科普。

【今日市场概况】
{context_summary}

请严格返回以下JSON格式:
{{
  "concept": "一个与今日市场相关的专业概念",
  "definition": "专业定义（1句话）",
  "plain_explanation": "说人话就是...",
  "today_example": "今天这个概念在市场中的真实体现"
}}

要求:
1. 概念要与今日市场实际发生的事情相关联
2. plain_explanation 用最通俗的语言解释
3. today_example 用今天的数据举例，让读者有具体感知"""

        system = (
            "你是一个擅长深入浅出的财经科普作者。请严格返回JSON。"
        )
        return self._call_deepseek(prompt, system, temperature=0.7, max_tokens=1500)

    def _gen_sector_review(self, prev_mentions: list, sector: dict, date: str) -> list:
        if not prev_mentions:
            return []

        today_plates = {}
        for p in sector.get('hot_plates_top5', []):
            if p.get('name'):
                today_plates[p['name']] = p

        review_data = []
        for m in prev_mentions:
            name = m['sector_name']
            today = today_plates.get(name, {})
            capital = today.get('capital_flow')
            capital_val = None
            if isinstance(capital, dict):
                capital_val = capital.get('main_net_inflow')
            review_data.append({
                'sector_name': name,
                'prev_change_pct': m.get('change_pct'),
                'prev_capital_flow_val': m.get('capital_flow_val'),
                'today_change_pct': today.get('change_pct'),
                'today_capital_flow_val': capital_val,
                'matched': bool(today),
            })

        data_summary = json.dumps({
            'date': date,
            'previous_sectors': prev_mentions,
            'today_data': review_data,
        }, ensure_ascii=False, default=str)

        prompt = f"""请基于以下数据，对上个交易日提到的板块进行简要复盘分析。

【数据汇总】
{data_summary}

请严格返回以下JSON格式:
{{
  "reviews": [
    {{
      "sector_name": "板块名称",
      "prev_change_pct": "昨日涨跌幅",
      "today_change_pct": "今日涨跌幅，无数据则写'已退出热门榜'",
      "continuation": "延续/反转/震荡",
      "analysis": "2-3句复盘：结合昨今数据变化分析板块当前所处阶段",
      "outlook": "后续关注点"
    }}
  ]
}}"""

        system = "你是一个专业的板块跟踪分析师，擅长结合行业基本面和技术面做复盘。请严格返回JSON。"
        result = self._call_deepseek(prompt, system, temperature=0.5, max_tokens=3000)
        if isinstance(result, dict) and 'reviews' in result:
            return result['reviews']
        if isinstance(result, list):
            return result
        return []

    # ── 阶段2: 多平台内容生成 ──

    COMPLIANCE_RULES = """【合规红线——严格遵守】
- 禁止出现具体股票代码（如600519.SH、00700.HK）
- 禁止给出买入/卖出/持有等任何投资建议
- 禁止使用"推荐""必涨""抄底""目标价""评分""利好""利空"等引导词
- 禁止对个股或板块做未来方向预测
- 如提及个股名称仅作为行业现象举例，最多2只，不做任何评价
- 结尾必须包含合规声明"""

    COMPLIANCE_DISCLAIMER = "本账号仅分享财经观察和学习笔记，不持有证券从业资格，内容不构成任何投资建议。投资有风险，入市需谨慎。"

    def _format_for_platform(self, raw_material: dict, platform: str,
                             user_instructions: str = None, goal: str = None,
                             modules: list = None) -> dict:
        if modules:
            filtered = {k: v for k, v in raw_material.items() if k in modules}
            material = filtered
        else:
            material = dict(raw_material)

        material_json = json.dumps(material, ensure_ascii=False, default=str)

        prompts = {
            'note': self._prompt_note,
            'shortVideo': self._prompt_short_video,
            'article': self._prompt_article,
        }

        builder = prompts.get(platform, self._prompt_note)
        prompt, system = builder(material_json, user_instructions, goal, modules)
        max_tokens = 12000 if platform == 'article' else 8000
        return self._call_deepseek(prompt, system, temperature=0.7, max_tokens=max_tokens)

    def _prompt_note(self, material_json: str, user_instructions: str = None, goal: str = None, modules: list = None):
        user_block = f"\n【用户自定义要求】\n{user_instructions}\n" if user_instructions else ""
        goal_block = self.GOAL_STRATEGIES.get(goal, '') if goal else ''

        all_modules = modules or ['market_overview', 'sector_review', 'hot_boards', 'hot_topics', 'knowledge_seed']

        structure_parts = ["""1. 钩子开头（1-2句）：必须制造"想点进来看"的冲动。从以下角度中选一个最匹配今日数据的：
   - 对比冲击型："一边是XX暴涨3%，一边是XX暴跌4%——今天的A股就是两个平行世界"
   - 数据冲击型："XX亿资金涌入一个方向，什么概念？"
   - 灵魂拷问型："如果只能买一个板块，你选哪个？"
   - 冷知识切入型："你知道今天最赚钱的板块和你家电费有什么关系吗？"
   禁止使用"你以为...其实..."句式"""]
        idx = 2
        if 'sector_review' in all_modules:
            structure_parts.append(f'{idx}. 昨日板块追踪（1句话）：如果有 sector_review，用一句话交代昨日提及板块的今日表现')
            idx += 1
        if 'market_overview' in all_modules:
            structure_parts.append(f'{idx}. 今日市场速写（1-2段）：不要罗列指数涨跌，用一个对比或比喻描述今天市场的"气质"')
            idx += 1
        if 'hot_boards' in all_modules:
            structure_parts.append(f"""{idx}. 热点板块故事（2-3段，核心段落）：选 1-2 个最有话题性的具体板块（如WiFi6、MiniLED等概念板块）深度展开。必须做到：
   - 抛出一个有争议的个人判断，并明确说"我可能错了，但我觉得..."
   - 用"因为→所以→但是"的结构制造转折感，不要一路看多
   - 必须关联一个普通人能感知的生活场景
   - 在板块分析段尾抛出一个选择题式提问""")
            idx += 1
        if 'hot_topics' in all_modules:
            structure_parts.append(f'{idx}. 热点话题（1段）：选最有争议性或与普通人最相关的话题')
            idx += 1
        if 'knowledge_seed' in all_modules:
            structure_parts.append(f'{idx}. 冷知识/概念科普（1段）：用"你绝对想不到"的语气引入')
            idx += 1
        structure_parts.append(f'{idx}. 合规声明："{self.COMPLIANCE_DISCLAIMER}"')
        structure_text = '\n'.join(structure_parts)

        prompt = f"""请将以下市场研究素材，转写为一篇有话题性、让人忍不住看完的财经观察笔记。

【素材内容】
{material_json}

请严格返回以下JSON格式:
{{
  "title": "标题（15字以内，带emoji）",
  "body": "正文内容（800-950字，必须写满800字以上）",
  "tags": ["#话题标签1", "#话题标签2", "...（5-8个）"],
  "cover_text": "封面文案（10-15字，对比+问句，以？结尾）"
}}

【标题要求——直接、具体、有冲击力】
标题必须包含至少一个具体数字（涨跌幅、资金量、个股数量），直接说出板块名，禁止模糊指代，15字以内。

【封面文案要求——对比+问句，10-15字】
公式：A事实 vs B事实 + 问句（以？结尾）

【正文结构】
{structure_text}

【写作风格——像人说话，不像AI】
- 像一个有态度的朋友在分享他今天看到的事，有判断、有犹豫、有转折
- 禁止"新闻联播式"的平铺直叙，每一段都要有一个让人"停下来想一想"的点
- 允许用"我觉得""说实话""可能我错了但是"这类主观表达
- 数据要"翻译"成人话
- 金融术语出现时必须立即用大白话解释
- 结尾段禁止鸡汤式感悟，必须用具体的选择题或预告收尾
- 话题标签包含 #财经日记 #今日吃瓜
- 【字数要求】正文body必须写满800字以上，目标850-950字
{goal_block}
{user_block}
{self.COMPLIANCE_RULES}"""

        system = (
            "你是一个有态度、有人味的财经观察者。你不是AI写手，你是一个真的每天盯盘、"
            "有自己判断、偶尔翻车但敢说的人。绝不荐股、不给投资建议。请严格返回JSON。"
        )
        return prompt, system

    def _prompt_short_video(self, material_json: str, user_instructions: str = None, goal: str = None, modules: list = None):
        user_block = f"\n【用户自定义要求】\n{user_instructions}\n" if user_instructions else ""
        goal_block = self.GOAL_STRATEGIES.get(goal, '') if goal else ''

        prompt = f"""请将以下市场研究素材，转写为一段财经短视频口播脚本。

【素材内容】
{material_json}

请严格返回以下JSON格式:
{{
  "title": "视频标题（15字以内，制造悬念感）",
  "body": "口播脚本全文（300-500字，约1-2分钟）",
  "tags": ["#话题标签1", "#话题标签2", "...（5-8个）"],
  "cover_text": "封面文字（一句话，10字以内）"
}}

【脚本结构】
1. 开场hook（1-2句，3秒抓注意力）：用反问或意外事实开场
2. 今天市场发生了啥（2-3句，15-20秒）：大盘表现+最有意思的现象
3. 热点板块故事（3-4句，20-30秒）：从热门板块中挑1-2个最有话题性的具体板块，关联日常生活
4. 知识彩蛋（2句，10秒）：一个冷知识或专业概念的大白话翻译
5. 互动结尾（1句，5秒）：引导评论
6. 口播合规声明（1句）："{self.COMPLIANCE_DISCLAIMER}"

【写作风格】
- 口语化，像面对镜头和观众说话
- 节奏快，每句话都有信息量，不废话
{goal_block}
{user_block}
{self.COMPLIANCE_RULES}"""

        system = (
            "你是一个财经短视频博主，擅长用30秒讲清一件事。"
            "风格：简洁有力、节奏感强、口语自然。绝不荐股。请严格返回JSON。"
        )
        return prompt, system

    def _prompt_article(self, material_json: str, user_instructions: str = None, goal: str = None, modules: list = None):
        user_block = f"\n【用户自定义要求】\n{user_instructions}\n" if user_instructions else ""
        goal_block = self.GOAL_STRATEGIES.get(goal, '') if goal else ''

        prompt = f"""请将以下市场研究素材，转写为一篇财经专栏风格的深度观察文章。

【素材内容】
{material_json}

请严格返回以下JSON格式:
{{
  "title": "文章标题（20字以内，专业但不晦涩）",
  "body": "正文内容（1500-2500字）",
  "tags": ["#话题标签1", "#话题标签2", "...（5-8个）"],
  "cover_text": "导语（一句话核心观点，20字以内）"
}}

【正文结构】
1. 导语（1段）：今日市场一句话定调+最值得关注的1个现象
2. 市场全景（2-3段）：大盘表现、成交量变化、市场情绪分析，用数据说话
3. 行业深度（4-5段）：从热门行业中挑2-3个深入分析，包含驱动因素、资金流向、产业逻辑、生活关联
4. 热点解读（1-2段）：今日最重要的财经事件/话题的深度解读
5. 知识延伸（1段）：一个与今日市场相关的专业概念深度解析
6. 风险与思考（1段）：客观讨论当前市场的不确定性
7. 合规声明："{self.COMPLIANCE_DISCLAIMER}"

【写作风格】
- 专业但不晦涩，像《财经》杂志的专栏作家
- 逻辑清晰，论据充分，数据精确
- 话题标签包含 #财经观察 #市场深度
{goal_block}
{user_block}
{self.COMPLIANCE_RULES}"""

        system = (
            "你是一个资深财经专栏作者，擅长用深入浅出的方式解读市场。"
            "绝不荐股、不给投资建议。请严格返回JSON。"
        )
        return prompt, system

    # ── DeepSeek 调用 ──

    def _call_deepseek(self, prompt: str, system_message: str,
                       temperature: float = 0.5, max_tokens: int = 4000) -> dict:
        api_key = self._api_key
        if not api_key:
            raise Exception("未配置 DEEPSEEK_API_KEY")

        import re
        clean_prompt = re.sub(r'\s+', ' ', prompt).strip()

        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": clean_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        }

        logger.info("[ContentOps] DeepSeek API 调用中...")
        response = requests.post(
            'https://api.deepseek.com/v1/chat/completions',
            headers=headers, json=payload, timeout=180,
        )

        if response.status_code != 200:
            raise Exception(f"DeepSeek API 错误: {response.status_code} {response.text[:200]}")

        result = response.json()
        usage = result.get('usage', {})
        logger.info(f"[ContentOps] DeepSeek 完成: tokens={usage.get('total_tokens', 0)}")

        msg = result['choices'][0]['message']
        content = msg.get('content') or ''
        if not content.strip():
            raise Exception("DeepSeek 返回内容为空")
        return json.loads(content)

    # ── 存储 ──

    def _ensure_schema(self):
        from service.storage.database_manager import db_manager
        db_manager.execute_update("""
            CREATE TABLE IF NOT EXISTS xhs_content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_date TEXT NOT NULL,
                stage TEXT DEFAULT 'raw',
                raw_material TEXT,
                xhs_title TEXT,
                xhs_body TEXT,
                xhs_tags TEXT,
                xhs_cover_text TEXT,
                verification_result TEXT,
                verified_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        for col, col_type in [('verification_result', 'TEXT'), ('verified_at', 'TIMESTAMP')]:
            try:
                db_manager.execute_update(f"ALTER TABLE xhs_content ADD COLUMN {col} {col_type}")
            except Exception:
                pass
        try:
            db_manager.execute_update("""
                CREATE TABLE IF NOT EXISTS content_sector_mentions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_id INTEGER NOT NULL,
                    content_date TEXT NOT NULL,
                    sector_name TEXT NOT NULL,
                    sector_symbol TEXT,
                    change_pct REAL,
                    capital_flow_val REAL,
                    source TEXT DEFAULT 'hot_sectors',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            db_manager.execute_update("""
                CREATE INDEX IF NOT EXISTS idx_sector_mentions_date
                ON content_sector_mentions(content_date)
            """)
        except Exception:
            pass

    def _save_content(self, date: str, stage: str, raw_material: dict) -> int:
        from service.storage.database_manager import db_manager
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return db_manager.execute_update(
            """INSERT INTO xhs_content (content_date, stage, raw_material, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (date, stage, json.dumps(raw_material, ensure_ascii=False, default=str), now, now)
        )

    def _save_sector_mentions(self, content_id: int, date: str, hot_sectors: list,
                              raw_plates: list = None):
        from service.storage.database_manager import db_manager

        plates_by_name = {}
        plates_list = []
        for p in (raw_plates or []):
            if isinstance(p, dict) and p.get('name'):
                plates_by_name[p['name']] = p
                plates_list.append(p)

        for s in (hot_sectors or []):
            if not isinstance(s, dict) or not s.get('sector_name'):
                continue
            name = s['sector_name']
            raw_plate = plates_by_name.get(name)
            if not raw_plate:
                for p in plates_list:
                    pname = p.get('name', '')
                    if name in pname or pname in name:
                        raw_plate = p
                        break
            raw_plate = raw_plate or {}

            symbol = raw_plate.get('symbol', '') or s.get('symbol', '')

            capital_val = None
            raw_cf = raw_plate.get('capital_flow')
            if isinstance(raw_cf, dict):
                capital_val = raw_cf.get('main_net_inflow')
            if capital_val is None:
                cf = s.get('capital_flow')
                if isinstance(cf, dict):
                    capital_val = cf.get('main_net_inflow')

            change_pct = None
            cp = raw_plate.get('change_pct') if raw_plate else None
            if cp is None:
                cp = s.get('change_pct')
            if cp is not None:
                try:
                    change_pct = float(str(cp).replace('%', '').replace('+', ''))
                except (ValueError, TypeError):
                    pass

            try:
                db_manager.execute_update(
                    """INSERT INTO content_sector_mentions
                       (content_id, content_date, sector_name, sector_symbol, change_pct, capital_flow_val, source)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (content_id, date, name, symbol, change_pct, capital_val, 'hot_sectors')
                )
            except Exception as e:
                logger.warning(f"[ContentOps] 保存板块提及失败: {e}")

    def _get_previous_mentions(self) -> list:
        from service.storage.database_manager import db_manager
        today = datetime.now().strftime('%Y-%m-%d')
        rows = db_manager.execute_query(
            """SELECT DISTINCT sector_name, sector_symbol, change_pct, capital_flow_val, content_date
               FROM content_sector_mentions
               WHERE content_date < ?
               ORDER BY content_date DESC, id DESC
               LIMIT 10""",
            (today,)
        )
        if not rows:
            return []
        latest_date = rows[0]['content_date']
        return [dict(r) for r in rows if r['content_date'] == latest_date]

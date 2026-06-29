"""
妙想数据客户端 — 基于东方财富妙想 SKILL API 的统一数据查询工具类

能力:
- 智能选股: 自然语言条件筛选股票（涨停/涨幅/市盈率/行业等）
- 金融数据: 个股行情、财务指标、资金流向、历史数据
- 资讯搜索: 新闻/公告/研报搜索

用法:
    from service.datapip.miaoxiang_client import MiaoXiangClient
    mx = MiaoXiangClient()
    stocks = mx.select_stocks("今日涨停的A股")
    data = mx.query_data("贵州茅台最新价涨跌幅")
    news = mx.search_news("芯片行业最新消息")
"""

import os
import json
import logging
import re
from typing import Dict, List, Any, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30


class MiaoXiangError(Exception):
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


class MiaoXiangClient:
    """东方财富妙想数据统一客户端"""

    URL_SELECT = "https://mkapi2.dfcfs.com/finskillshub/api/claw/stock-screen"
    URL_DATA = "https://mkapi2.dfcfs.com/finskillshub/api/claw/query"
    URL_SEARCH = "https://mkapi2.dfcfs.com/finskillshub/api/claw/news-search"

    def __init__(self, api_key: Optional[str] = None, timeout: int = _DEFAULT_TIMEOUT):
        self.api_key = api_key or os.getenv("MX_APIKEY")
        if not self.api_key:
            raise MiaoXiangError("MX_APIKEY 未设置，请配置环境变量或传入 api_key 参数")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json",
            "apikey": self.api_key,
        })

    # ═══════════════════════════════════════
    # 智能选股
    # ═══════════════════════════════════════

    def select_stocks(self, query: str) -> List[Dict[str, Any]]:
        """
        智能选股：自然语言条件 → 股票列表

        Args:
            query: 自然语言条件，如 "今日涨停的A股"、"市盈率小于20的银行股"

        Returns:
            股票列表，每只股票为字典，键为中文列名
            示例: [{'代码': '601066', '名称': '中信建投', '最新价': 30.5, '涨跌幅(%)': 9.99, ...}]
        """
        result = self._post(self.URL_SELECT, {"keyword": query})
        rows, source, err = self._extract_select_data(result)
        if err:
            logger.warning(f"[MiaoXiang] 选股失败: {err}")
            return []
        return rows

    def select_stocks_raw(self, query: str) -> Dict[str, Any]:
        """选股并返回完整原始响应（含统计信息、筛选条件等）"""
        return self._post(self.URL_SELECT, {"keyword": query})

    def get_market_breadth(self) -> Dict[str, int]:
        """并行获取今日 A 股上涨/下跌/平盘家数。
        上涨/下跌并发查询，平盘用涨跌额=0单独串行查询（避免3并发触发限流）。
        """
        from concurrent.futures import ThreadPoolExecutor

        def _fetch_count(keyword: str) -> int:
            try:
                raw = self.select_stocks_raw(keyword)
                if not raw:
                    return 0
                conds = (raw.get('data', {}).get('data', {})
                            .get('responseConditionList', []))
                return next(
                    (int(c['stockCount']) for c in conds
                     if '证券类型' not in c.get('describe', '')
                     and '股票代码' not in c.get('describe', '')),
                    0
                )
            except Exception:
                return 0

        with ThreadPoolExecutor(max_workers=2) as pool:
            f_up   = pool.submit(_fetch_count, "今日A股上涨的股票")
            f_down = pool.submit(_fetch_count, "今日A股下跌的股票")
            advance = f_up.result()
            decline = f_down.result()

        flat = _fetch_count("今日涨跌额为0的A股")
        return {'advance': advance, 'decline': decline, 'flat': flat}

    def get_limit_up_stocks(self) -> List[Dict[str, Any]]:
        """获取今日涨停股"""
        return self.select_stocks("今日涨停的A股")

    def get_limit_down_stocks(self) -> List[Dict[str, Any]]:
        """获取今日跌停股"""
        return self.select_stocks("今日跌停的A股")

    def get_top_gainers(self, pct: float = 5.0) -> List[Dict[str, Any]]:
        """获取今日涨幅大于指定百分比的股票"""
        return self.select_stocks(f"今日涨幅大于{pct}%的A股")

    def get_top_losers(self, pct: float = -5.0) -> List[Dict[str, Any]]:
        """获取今日跌幅大于指定百分比的股票"""
        return self.select_stocks(f"今日跌幅大于{abs(pct)}%的A股")

    def get_high_volume_stocks(self, turnover_rate: float = 10.0) -> List[Dict[str, Any]]:
        """获取换手率大于指定值的股票"""
        return self.select_stocks(f"今日换手率大于{turnover_rate}%的A股")

    def get_stocks_by_sector(self, sector: str, condition: str = "") -> List[Dict[str, Any]]:
        """获取指定板块/行业的股票，可附加筛选条件"""
        query = f"{sector}板块{condition}的股票" if condition else f"{sector}板块的股票"
        return self.select_stocks(query)

    def get_stocks_by_condition(self, conditions: List[str]) -> List[Dict[str, Any]]:
        """多条件组合选股"""
        query = " ".join(conditions) + " A股"
        return self.select_stocks(query)

    # ═══════════════════════════════════════
    # 金融数据查询
    # ═══════════════════════════════════════

    def query_data(self, query: str) -> List[Dict[str, Any]]:
        """
        金融数据查询：自然语言问句 → 结构化数据

        Args:
            query: 如 "贵州茅台最新价涨跌幅"、"宁德时代近三年净利润"

        Returns:
            数据表列表，每个表为字典含 'headers' 和 'rows'
        """
        result = self._post(self.URL_DATA, {"query": query})
        tables, _, total, err = self._extract_query_data(result)
        if err:
            logger.warning(f"[MiaoXiang] 数据查询失败: {err}")
            return []
        return tables

    def query_data_raw(self, query: str) -> Dict[str, Any]:
        """数据查询并返回完整原始响应"""
        return self._post(self.URL_DATA, {"query": query})

    def get_stock_quote(self, name_or_code: str) -> Dict[str, Any]:
        """获取单只股票实时行情"""
        tables = self.query_data(f"{name_or_code}最新价涨跌幅成交额换手率市盈率")
        if tables and tables[0].get('rows'):
            return tables[0]['rows'][0] if tables[0]['rows'] else {}
        return {}

    def get_stock_financials(self, name_or_code: str, years: int = 3) -> List[Dict[str, Any]]:
        """获取财务指标"""
        tables = self.query_data(f"{name_or_code}近{years}年净利润营业收入净资产收益率")
        return tables

    def get_capital_flow(self, name_or_code: str) -> List[Dict[str, Any]]:
        """获取主力资金流向"""
        tables = self.query_data(f"{name_or_code}主力资金流向")
        return tables

    # ═══════════════════════════════════════
    # 资讯搜索
    # ═══════════════════════════════════════

    def search_news(self, query: str) -> str:
        """
        资讯搜索：返回格式化的新闻/公告/研报内容

        Args:
            query: 搜索关键词，如 "芯片行业最新消息"

        Returns:
            格式化的资讯文本
        """
        result = self._post(self.URL_SEARCH, {"query": query})
        return self._extract_search_content(result)

    def search_news_raw(self, query: str) -> Dict[str, Any]:
        """资讯搜索并返回完整原始响应"""
        return self._post(self.URL_SEARCH, {"query": query})

    # ═══════════════════════════════════════
    # 数据标准化
    # ═══════════════════════════════════════

    @staticmethod
    def normalize_stock_record(record: Dict[str, Any]) -> Dict[str, Any]:
        """
        将选股结果的动态列名（含时间后缀）标准化为固定键名

        Returns:
            {'code': '601066', 'name': '中信建投', 'price': 30.5,
             'change_pct': 9.99, 'market': 'SH', 'volume': ..., ...}
        """
        def find_val(*prefixes):
            """按中文列名前缀查找（列名映射成功时使用）"""
            for k, v in record.items():
                for p in prefixes:
                    if k.startswith(p):
                        return v
            return None

        def find_raw(*raw_subs):
            """按英文字段名子串查找（列名映射失败、key 保留原始英文时使用）"""
            for k, v in record.items():
                ku = k.upper()
                for s in raw_subs:
                    if s.upper() in ku:
                        return v
            return None

        high = find_val('最高价') or find_raw('PEAK_PRICE')
        low  = find_val('最低价') or find_raw('BOTTOM_PRICE')
        price = record.get('NEWEST_PRICE') or find_val('最新价')

        # 一字板：全天高==低（开盘即封板，无成交区间）
        def _is_yizi():
            try:
                return high is not None and low is not None and float(high) == float(low)
            except (TypeError, ValueError):
                return False

        return {
            'code': record.get('代码', '') or record.get('SECURITY_CODE', ''),
            'name': record.get('名称', '') or record.get('SECURITY_SHORT_NAME', ''),
            'market': record.get('市场代码简称', '') or record.get('MARKET_SHORT_NAME', ''),
            'price': price,
            'change_pct': find_val('涨跌幅') or record.get('CHG') or record.get('PCHG'),
            'change_val': find_val('涨跌额'),
            'high': high,
            'low': low,
            'volume': find_val('成交量') or find_raw('VOLUME'),
            'amount': find_val('成交额') or find_raw('TRADING_VOLUMES'),
            'turnover_rate': find_val('换手率') or find_raw('TURNOVER_RATE'),
            'volume_ratio': find_val('量比') or find_raw('LIANGBI'),
            'pe': find_val('市盈率') or find_raw('PE_D'),
            'pb': find_val('市净率') or find_raw('_PB'),
            'market_cap': find_val('总市值') or find_raw('TOAL_MARKET_VALUE'),
            'float_cap': find_val('流通市值') or find_raw('CIRCULATION_MARKET_VALUE'),
            'limit_up': find_val('涨停') or find_raw('IS_LIMIT_UP') or None,
            'first_limit_time': find_val('涨停首次封板时间') or find_raw('LIMIT_UP_FLT'),
            'limit_order_amount': find_val('涨停封单额') or find_raw('LIMIT_UP_A'),
            'is_first_board': find_val('首板') or find_raw('FIRST_LIMITUP'),
            'stock_type': record.get('证券类型', ''),
            'is_yizi_ban': _is_yizi(),
        }

    def select_stocks_normalized(self, query: str) -> List[Dict[str, Any]]:
        """选股并返回标准化字段名的结果"""
        raw = self.select_stocks(query)
        return [self.normalize_stock_record(r) for r in raw]

    # ═══════════════════════════════════════
    # 内部方法
    # ═══════════════════════════════════════

    def _post(self, url: str, payload: dict) -> Dict[str, Any]:
        """发送 POST 请求"""
        try:
            resp = self._session.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.Timeout:
            raise MiaoXiangError("请求超时", code="TIMEOUT")
        except requests.ConnectionError:
            raise MiaoXiangError("网络连接失败", code="CONNECTION_ERROR")
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 401:
                raise MiaoXiangError("API Key 无效或已过期", code="AUTH_ERROR")
            raise MiaoXiangError(f"HTTP 错误: {e}", code="HTTP_ERROR")
        except json.JSONDecodeError:
            raise MiaoXiangError("响应解析失败", code="PARSE_ERROR")

    @staticmethod
    def _extract_select_data(result: Dict[str, Any]) -> Tuple[List[Dict], str, Optional[str]]:
        """从选股响应提取结构化数据"""
        status = result.get("status")
        if status != 0:
            return [], "", f"状态码 {status}: {result.get('message', '')}"

        data = result.get("data", {})
        inner = data.get("data", {})

        # 优先 allResults.result.dataList
        all_results = inner.get("allResults", {}).get("result", {})
        data_list = all_results.get("dataList", [])
        columns = all_results.get("columns", [])

        if isinstance(data_list, list) and data_list:
            column_map = MiaoXiangClient._build_column_map(columns)
            order = MiaoXiangClient._columns_order(columns)
            rows = MiaoXiangClient._datalist_to_rows(data_list, column_map, order)
            return rows, "dataList", None

        # 回退 partialResults
        partial = inner.get("partialResults", "")
        if partial:
            rows = MiaoXiangClient._parse_markdown_table(partial)
            return rows, "partialResults", None

        return [], "", "无有效数据"

    @staticmethod
    def _extract_query_data(result: Dict[str, Any]) -> Tuple[List[Dict], List[str], int, Optional[str]]:
        """从数据查询响应提取表格数据"""
        status = result.get("status")
        if status != 0:
            return [], [], 0, f"状态码 {status}: {result.get('message', '')}"

        data = result.get("data", {})
        inner = data.get("data", {})
        blocks = inner.get("allResults", [])

        if not isinstance(blocks, list) or not blocks:
            # 尝试 partialResults
            partial = inner.get("partialResults", "")
            if partial:
                return [{'headers': [], 'rows': MiaoXiangClient._parse_markdown_table(partial)}], [], 0, None
            return [], [], 0, "无有效数据"

        tables = []
        total_rows = 0
        for block in blocks:
            if not isinstance(block, dict):
                continue
            table_data = block.get("result", block)
            if isinstance(table_data, dict):
                data_list = table_data.get("dataList", [])
                columns = table_data.get("columns", [])
                if data_list:
                    col_map = MiaoXiangClient._build_column_map(columns)
                    order = MiaoXiangClient._columns_order(columns)
                    rows = MiaoXiangClient._datalist_to_rows(data_list, col_map, order)
                    tables.append({'headers': list(rows[0].keys()) if rows else [], 'rows': rows})
                    total_rows += len(rows)

        return tables, [], total_rows, None

    @staticmethod
    def _extract_search_content(result: Dict[str, Any]) -> str:
        """从资讯搜索响应提取文本"""
        status = result.get("status")
        if status != 0:
            return f"搜索失败: {result.get('message', '')}"

        data = result.get("data", {})
        inner = data.get("data", {})

        # 尝试提取 content / answer / partialResults
        for key in ("content", "answer", "partialResults"):
            val = inner.get(key)
            if val and isinstance(val, str):
                return val

        return json.dumps(inner, ensure_ascii=False, indent=2) if inner else "无结果"

    # ── 数据解析工具 ──

    @staticmethod
    def _build_column_map(columns: List[Dict]) -> Dict[str, str]:
        name_map = {}
        for col in columns or []:
            if not isinstance(col, dict):
                continue
            en_key = col.get("field", "") or col.get("name", "") or col.get("key", "")
            cn_name = col.get("displayName", "") or col.get("title", "") or col.get("label", "")
            date_msg = col.get("dateMsg", "")
            if date_msg:
                cn_name = f"{cn_name} {date_msg}"
            if en_key and cn_name:
                name_map[str(en_key)] = str(cn_name)
        return name_map

    @staticmethod
    def _columns_order(columns: List[Dict]) -> List[str]:
        order = []
        for col in columns or []:
            if not isinstance(col, dict):
                continue
            en_key = col.get("field") or col.get("name") or col.get("key")
            if en_key:
                order.append(str(en_key))
        return order

    @staticmethod
    def _datalist_to_rows(datalist: List[Dict], column_map: Dict[str, str],
                          column_order: List[str]) -> List[Dict[str, str]]:
        if not datalist:
            return []
        first = datalist[0]
        extra_keys = [k for k in first if k not in column_order]
        header_order = column_order + extra_keys

        rows = []
        for row in datalist:
            if not isinstance(row, dict):
                continue
            cn_row = {}
            for en_key in header_order:
                if en_key not in row:
                    continue
                cn_name = column_map.get(en_key, en_key)
                val = row[en_key]
                if val is None:
                    cn_row[cn_name] = ""
                elif isinstance(val, (dict, list)):
                    cn_row[cn_name] = json.dumps(val, ensure_ascii=False)
                else:
                    cn_row[cn_name] = val

            rows.append(cn_row)
        return rows

    @staticmethod
    def _parse_markdown_table(text: str) -> List[Dict[str, str]]:
        if not text or not isinstance(text, str):
            return []
        lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
        if not lines:
            return []

        def split_cells(line):
            return [c.strip() for c in line.split("|") if c.strip()]

        header = split_cells(lines[0])
        if not header:
            return []

        start = 1
        if start < len(lines) and re.match(r"^[\s|\\-]+$", lines[start]):
            start = 2

        rows = []
        for i in range(start, len(lines)):
            cells = split_cells(lines[i])
            if len(cells) < len(header):
                cells.extend([""] * (len(header) - len(cells)))
            elif len(cells) > len(header):
                cells = cells[:len(header)]
            rows.append(dict(zip(header, cells)))
        return rows

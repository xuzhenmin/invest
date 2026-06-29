"""金融数据查询工具类。

封装金融数据 API 的三步调用流程（工具召回→实体识别→正式查询），
提供标准化的利润表、现金流量表、资产负债表等金融数据查询能力。

API 协议版本: V2
数据源: 通过环境变量 FINANCIAL_DATA_BASE_URL 配置
"""
import json
import os
import re
import time
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeoutError

import requests as _requests

try:
    from utils.logger_config import get_logger
    logger = get_logger("financial_data_client")
except Exception:
    import logging
    logger = logging.getLogger("financial_data_client")

_DEFAULT_BASE_URL = os.environ.get("FINANCIAL_DATA_BASE_URL", "").rstrip("/")
if not _DEFAULT_BASE_URL:
    raise EnvironmentError("FINANCIAL_DATA_BASE_URL 未配置，请在 .env 中设置该环境变量")
_DEFAULT_TIMEOUT = 120
_BATCH_TIMEOUT = 300
_MAX_BATCH_SIZE = 20
_MAX_PARAMS_SIZE = 10000
_MAX_CONCURRENCY = 10
_MAX_RETRIES = 3
_MAX_INPUT_TEXTS = 50

_RETRYABLE_CODES = frozenset({"TIMEOUT", "API_ERROR", "BIZ_ERROR"})
_NON_RETRYABLE_STATUSES = frozenset({
    "INVALID_SYMBOL", "BAD_REQUEST", "MISSING_API_KEY", "AUTH_FAILED",
})
_ALLOWED_PATH_PREFIXES = ("/api/",)
_KNOWN_HOSTS = [
    _DEFAULT_BASE_URL,
    _DEFAULT_BASE_URL.removeprefix("https://").removeprefix("http://"),
]

# 财务报表工具召回意图关键词
_STATEMENT_INTENTS = {
    "income": "利润表查询",
    "cashflow": "现金流量表查询",
    "balance": "资产负债表查询",
}


class FinancialDataError(Exception):
    """金融数据查询异常。"""

    def __init__(self, message, code="INTERNAL_ERROR", upstream_status=None):
        super().__init__(message)
        self.code = code
        self.upstream_status = upstream_status


class FinancialDataClient:
    """金融数据查询工具类。

    封装三步调用流程:
    1. tool_recall  — 根据意图召回候选 API 工具
    2. entity_resolve — 将股票名称解析为标准代码
    3. query — 批量执行数据查询

    Args:
        api_key: API 密钥，为空时从环境变量 FINANCIAL_DATA_API_KEY 读取
        base_url: API 基础地址，默认为生产环境
        timeout: 单次请求超时秒数
    """

    def __init__(self, api_key=None, base_url=None, timeout=_DEFAULT_TIMEOUT):
        self._api_key = api_key or os.environ.get("FINANCIAL_DATA_API_KEY", "").strip()
        if not self._api_key:
            raise FinancialDataError(
                "API 密钥未设置。请传入 api_key 参数或设置环境变量 FINANCIAL_DATA_API_KEY",
                code="CONFIG_ERROR",
            )
        self._base_url = (base_url or _DEFAULT_BASE_URL).rstrip("/")
        self._timeout = timeout
        self._tool_cache = None
        self._tool_cache_time = 0
        self._tool_cache_ttl = 86400
        self._lock = threading.Lock()
        # 复用 Session：避免每次请求都重新 TCP/TLS 握手
        self._session = _requests.Session()

    def _headers(self):
        return {
            "X-API-Key": self._api_key,
            "X-API-Version": "2",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # 底层 HTTP
    # ------------------------------------------------------------------

    def _post(self, path, payload, timeout=None, max_retries=_MAX_RETRIES, session=None):
        """发送 POST 请求，带重试和 V2 响应解包。"""
        if not path.startswith("/"):
            path = "/" + path
        timeout = timeout or self._timeout
        poster = session or self._session or _requests

        last_error = None
        for attempt in range(max_retries):
            try:
                resp = poster.post(
                    f"{self._base_url}{path}",
                    headers=self._headers(),
                    json=payload,
                    timeout=timeout,
                    allow_redirects=False,
                    verify=True,
                )
                if not resp.ok:
                    body = None
                    try:
                        body = resp.json()
                    except (ValueError, json.JSONDecodeError):
                        pass
                    if isinstance(body, dict) and isinstance(body.get("status"), str):
                        msg = body.get("message") or "业务错误"
                        raise FinancialDataError(
                            f"[{body['status']}] {msg}",
                            code="BIZ_ERROR",
                            upstream_status=body["status"],
                        )
                    raise FinancialDataError(f"HTTP {resp.status_code}", code="API_ERROR")

                if 300 <= resp.status_code < 400:
                    raise FinancialDataError(
                        f"HTTP {resp.status_code} 重定向", code="API_ERROR"
                    )

                result = resp.json()
                return self._unwrap_v2(result)

            except FinancialDataError as e:
                is_retryable = (
                    e.code in _RETRYABLE_CODES
                    and e.upstream_status not in _NON_RETRYABLE_STATUSES
                )
                if is_retryable and attempt < max_retries - 1:
                    last_error = e
                    time.sleep(1 * (attempt + 1))
                    logger.warning("请求 %s 第 %d 次重试: %s", path, attempt + 1, e)
                    continue
                raise

            except _requests.exceptions.Timeout as e:
                err = FinancialDataError(f"请求超时 ({timeout}s)", code="TIMEOUT")
                if attempt < max_retries - 1:
                    last_error = err
                    time.sleep(1 * (attempt + 1))
                    logger.warning("请求 %s 超时, 第 %d 次重试", path, attempt + 1)
                    continue
                raise err from e

            except _requests.exceptions.RequestException as e:
                logger.error("网络错误: %s", e)
                err = FinancialDataError(
                    f"网络错误 ({type(e).__name__})", code="API_ERROR"
                )
                if attempt < max_retries - 1:
                    last_error = err
                    time.sleep(1 * (attempt + 1))
                    continue
                raise err from e

        raise last_error

    def _unwrap_v2(self, result):
        """解析 V2 协议响应信封。"""
        if not isinstance(result, dict):
            return result
        if "code" not in result or "status" not in result:
            return result
        status_val = result["status"]
        if not isinstance(status_val, str):
            return result
        try:
            code_val = int(result["code"])
        except (TypeError, ValueError):
            return result
        if code_val != 200:
            msg = result.get("message") or "业务错误"
            raise FinancialDataError(
                f"[{status_val}] {msg}",
                code="BIZ_ERROR",
                upstream_status=status_val,
            )
        return result

    # ------------------------------------------------------------------
    # URL 校验
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_url(url):
        """校验 API 路径安全性。"""
        if not isinstance(url, str) or not url.strip():
            raise FinancialDataError("url 无效", code="PARSE_ERROR")
        url = url.strip()
        # 自动剥离已知域名前缀
        for host in _KNOWN_HOSTS:
            if url.startswith(host):
                rest = url[len(host):]
                if rest and not rest.startswith("/"):
                    continue
                url = rest if rest else "/"
                break
        if "://" in url:
            raise FinancialDataError("url 不允许包含协议前缀", code="PARSE_ERROR")
        if not url.startswith("/"):
            url = "/" + url
        decoded = url
        for _ in range(5):
            prev = decoded
            decoded = urllib.parse.unquote(decoded)
            if decoded == prev:
                break
        if ".." in decoded.split("/"):
            raise FinancialDataError("url 不允许包含路径遍历", code="PARSE_ERROR")
        if not any(decoded.startswith(p) for p in _ALLOWED_PATH_PREFIXES):
            raise FinancialDataError(
                f"url 必须以 /api/ 开头, 当前: {url}", code="PARSE_ERROR"
            )
        return url

    # ------------------------------------------------------------------
    # 三个核心方法
    # ------------------------------------------------------------------

    def tool_recall(self, intents, score=None):
        """工具召回：根据意图关键词匹配候选 API 工具。

        Args:
            intents: 意图列表，如 ["利润表查询", "现金流量表查询"]
            score: 相关性阈值 0~1，None 表示使用服务端默认值

        Returns:
            dict: 包含 results 列表的响应，每个工具含 name/url/request/response 等字段

        Raises:
            FinancialDataError: API 调用失败
        """
        if isinstance(intents, str):
            intents = [intents]
        if not intents or len(intents) > _MAX_INPUT_TEXTS:
            raise FinancialDataError(
                f"intents 须为 1~{_MAX_INPUT_TEXTS} 项的非空列表",
                code="PARSE_ERROR",
            )
        payload = {"input_texts": [t.strip() for t in intents]}
        if score is not None:
            if not 0 <= score <= 1:
                raise FinancialDataError("score 须在 0~1 之间", code="PARSE_ERROR")
            payload["score"] = score

        data = self._post("/api/v1/agent/financial-tool-recall", payload)
        if isinstance(data, dict):
            raw_list = data.get("results", [])
        elif isinstance(data, list):
            raw_list = data
        else:
            raw_list = []
        tools = []
        for i, tool in enumerate(raw_list):
            if isinstance(tool, dict) and tool.get("url"):
                t = dict(tool)
                t["index"] = i
                tools.append(t)
        if isinstance(data, dict):
            return {**data, "results": tools}
        return {"results": tools}

    def entity_resolve(self, names):
        """实体识别：将股票名称解析为标准证券代码。

        Args:
            names: 名称列表，如 ["屹唐股份", "贵州茅台"]

        Returns:
            dict: 包含 results 列表，每项含 symbol/secu_abbr/asset_type 等字段

        Raises:
            FinancialDataError: API 调用失败
        """
        if isinstance(names, str):
            names = [names]
        if not names or len(names) > _MAX_INPUT_TEXTS:
            raise FinancialDataError(
                f"names 须为 1~{_MAX_INPUT_TEXTS} 项的非空列表",
                code="PARSE_ERROR",
            )
        data = self._post(
            "/api/v1/agent/nl2entity",
            {"input_texts": [n.strip() for n in names]},
        )
        if isinstance(data, list):
            return {"results": data}
        if isinstance(data, dict):
            return data
        return {"results": []}

    def query(self, requests_list):
        """批量数据查询：并发执行多个 API 请求。

        Args:
            requests_list: 请求列表，每项为 {"url": "/api/v1/...", "params": {...}, "label": "可选标签"}

        Returns:
            dict: {total, success, failed, results: [{ok, data, ...}, ...]}

        Raises:
            FinancialDataError: 输入校验失败（非单项查询失败）
        """
        if isinstance(requests_list, dict):
            requests_list = [requests_list]
        if not requests_list:
            raise FinancialDataError("请求列表不能为空", code="PARSE_ERROR")
        if len(requests_list) > _MAX_BATCH_SIZE:
            raise FinancialDataError(
                f"单批最多 {_MAX_BATCH_SIZE} 个请求", code="PARSE_ERROR"
            )
        for idx, item in enumerate(requests_list):
            if not isinstance(item, dict) or "url" not in item or "params" not in item:
                raise FinancialDataError(f"第 {idx} 项缺少 url 或 params", code="PARSE_ERROR")
            item["url"] = self._validate_url(item["url"])
            if not isinstance(item["params"], dict):
                raise FinancialDataError(f"第 {idx} 项 params 须为 dict", code="PARSE_ERROR")
            params_str = json.dumps(item["params"], ensure_ascii=False)
            if len(params_str) > _MAX_PARAMS_SIZE:
                raise FinancialDataError(
                    f"第 {idx} 项 params 过大 ({len(params_str)} 字符)",
                    code="PARSE_ERROR",
                )

        results = self._run_batch(requests_list)
        n_success = sum(1 for r in results if r and r.get("ok"))
        return {
            "total": len(results),
            "success": n_success,
            "failed": len(results) - n_success,
            "results": results,
        }

    # ------------------------------------------------------------------
    # 批量并发执行
    # ------------------------------------------------------------------

    def _run_batch(self, batch):
        """并发执行批量请求，每项隔离互不影响。"""
        results = [None] * len(batch)
        concurrency = min(len(batch), _MAX_CONCURRENCY)
        thread_local = threading.local()
        sessions = []
        sessions_lock = threading.Lock()

        def get_session():
            if not hasattr(thread_local, "session"):
                s = _requests.Session()
                s.verify = True
                thread_local.session = s
                with sessions_lock:
                    sessions.append(s)
            return thread_local.session

        def execute_one(url, params):
            return self._post(url, params, timeout=_DEFAULT_TIMEOUT, session=get_session())

        executor = ThreadPoolExecutor(max_workers=concurrency)
        try:
            futures = {
                executor.submit(execute_one, item["url"], item["params"]): idx
                for idx, item in enumerate(batch)
            }
            for future in as_completed(futures, timeout=_BATCH_TIMEOUT):
                idx = futures[future]
                entry = {}
                label = batch[idx].get("label")
                if label:
                    entry["label"] = label
                try:
                    data = future.result(timeout=0)
                    entry.update({"ok": True, "data": data})
                except FinancialDataError as e:
                    entry.update({"ok": False, "code": e.code, "data": None, "error": str(e)})
                except Exception as e:
                    entry.update({"ok": False, "code": "INTERNAL_ERROR", "data": None, "error": str(e)})
                results[idx] = entry

        except FuturesTimeoutError:
            for future, idx in futures.items():
                if results[idx] is not None:
                    continue
                if future.done():
                    entry = {}
                    label = batch[idx].get("label")
                    if label:
                        entry["label"] = label
                    try:
                        data = future.result(timeout=0)
                        entry.update({"ok": True, "data": data})
                    except Exception as e:
                        entry.update({"ok": False, "code": "INTERNAL_ERROR", "data": None, "error": str(e)})
                    results[idx] = entry
            for idx, r in enumerate(results):
                if r is None:
                    entry = {}
                    label = batch[idx].get("label")
                    if label:
                        entry["label"] = label
                    entry.update({
                        "ok": False, "code": "TIMEOUT",
                        "data": None, "error": f"批量整体超时 ({_BATCH_TIMEOUT}s)",
                    })
                    results[idx] = entry
        finally:
            executor.shutdown(wait=False)
            for s in sessions:
                try:
                    s.close()
                except Exception:
                    pass

        return results

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _resolve_symbol(self, symbol_or_name):
        """解析股票代码。已是标准代码格式则直接返回，否则调用实体识别。"""
        if re.match(r"^\d{6}\.[A-Z]{2}$", symbol_or_name.strip()):
            return symbol_or_name.strip()
        result = self.entity_resolve([symbol_or_name])
        entities = result.get("results", [])
        if not entities:
            raise FinancialDataError(
                f"无法识别标的: {symbol_or_name}", code="BIZ_ERROR"
            )
        for e in entities:
            if e.get("asset_type") == "股票":
                return e["symbol"]
        return entities[0]["symbol"]

    @staticmethod
    def _to_list(value):
        """将 str 或 list 统一为 list。"""
        if isinstance(value, str):
            return [value]
        return list(value)

    def _query_single(self, url, params):
        """单接口直接查询，返回 API 原始响应 dict。"""
        return self._post(url, params)

    def _symbols_params(self, symbols, start_date=None, end_date=None, fields=None, **extra):
        """构造 symbols + 可选时间/字段 的通用参数 dict。"""
        p = {"symbols": self._to_list(symbols)}
        if start_date:
            p["start_date"] = start_date
        if end_date:
            p["end_date"] = end_date
        if fields:
            p["fields"] = self._to_list(fields)
        p.update(extra)
        return p

    def _get_cached_tools(self, intents):
        """获取工具召回结果，带 TTL 缓存。"""
        cache_key = tuple(sorted(intents))
        with self._lock:
            if (
                self._tool_cache
                and self._tool_cache.get("key") == cache_key
                and time.time() - self._tool_cache_time < self._tool_cache_ttl
            ):
                return self._tool_cache["data"]

        data = self.tool_recall(intents)
        with self._lock:
            self._tool_cache = {"key": cache_key, "data": data}
            self._tool_cache_time = time.time()
        return data

    # ==================================================================
    # 便捷方法：财务报表
    # ==================================================================

    def get_financial_statements(self, symbol_or_name, start_date, end_date,
                                statements=None):
        """一步到位查询财务报表数据（资产负债表 + 利润现金流量表）。

        自动执行: 工具召回(缓存) → 实体识别(按需) → 批量查询

        Args:
            symbol_or_name: 股票代码或名称
            start_date/end_date: "yyyy-MM-dd"
            statements: ["income", "cashflow", "balance"]，默认全部
        """
        if statements is None:
            statements = ["income", "cashflow", "balance"]

        symbol = self._resolve_symbol(symbol_or_name)
        logger.info("查询 %s (%s) 财务报表: %s ~ %s", symbol_or_name, symbol, start_date, end_date)

        intents = list({_STATEMENT_INTENTS[s] for s in statements if s in _STATEMENT_INTENTS})
        tools_data = self._get_cached_tools(intents)
        tools = tools_data.get("results", [])

        batch = []
        for tool in tools:
            name = tool.get("name", "")
            url = tool.get("url", "")
            params = {"symbols": [symbol], "start_date": start_date, "end_date": end_date}
            if "资产负债表" in name and ("balance" in statements):
                batch.append({"url": url, "params": params, "label": "balance_sheet"})
            elif "利润与现金流量表(累计)" in name and (
                "income" in statements or "cashflow" in statements
            ):
                batch.append({"url": url, "params": params, "label": "income_cashflow"})

        if not batch:
            raise FinancialDataError("未找到匹配的财务报表查询工具", code="BIZ_ERROR")

        query_result = self.query(batch)
        output = {"symbol": symbol, "query_result": query_result}
        for item in query_result.get("results", []):
            label = item.get("label")
            if label and item.get("ok"):
                output[label] = item["data"]
        return output

    def get_balance_sheet(self, symbols, start_date=None, end_date=None, fields=None):
        """资产负债表（A股/港股/美股，季频）。"""
        return self._query_single(
            "/api/v1/stock_fnd/balance-sheet",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    def get_income_cashflow(self, symbols, start_date=None, end_date=None, fields=None):
        """利润与现金流量表 — 累计（年初至报告期末）。"""
        return self._query_single(
            "/api/v1/stock_fnd/income-cashflow-acc",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    def get_income_cashflow_single(self, symbols, start_date=None, end_date=None, fields=None):
        """利润与现金流量表 — 单季。"""
        return self._query_single(
            "/api/v1/stock_fnd/income-cashflow-single",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    def get_index_financial_statement(self, symbols, start_date=None, end_date=None, fields=None):
        """指数财务报表（聚合后的核心科目）。"""
        return self._query_single(
            "/api/v1/index_fnd/index-fnd-financial-statement",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    # ==================================================================
    # 便捷方法：实时行情
    # ==================================================================

    def get_snapshot(self, symbols, fields=None):
        """实时行情快照（最新价/涨跌幅/成交量/涨停价等）。"""
        return self._query_single(
            "/api/v1/quote/basic-snapshot",
            self._symbols_params(symbols, fields=fields),
        )

    def get_derived_snapshot(self, symbols, fields=None):
        """衍生快照（总市值/流通市值/换手率/PE/PB/EPS等）。"""
        return self._query_single(
            "/api/v1/quote/derived-snapshot",
            self._symbols_params(symbols, fields=fields),
        )

    def get_kline(self, symbols, period=None, split=None,
                  start_date=None, end_date=None, count=None, fields=None):
        """K线批量查询（日/周/月，支持复权）。

        Args:
            period: "daily"/"weekly"/"monthly" 等
            split: 复权类型
            count: 返回条数上限
        """
        extra = {}
        if period:
            extra["period"] = period
        if split:
            extra["split"] = split
        if count is not None:
            extra["count"] = count
        return self._query_single(
            "/api/v1/quote/kline-batch",
            self._symbols_params(symbols, start_date, end_date, fields, **extra),
        )

    def get_capital_flow(self, symbol, period=None,
                         start_date=None, end_date=None, count=None, fields=None):
        """资金流向（主力/散户流入流出，支持日/周/月）。

        Args:
            symbol: 单个标的代码（str）
            period: "P_Day1"/"P_Week1"/"P_Month1"/"P_Year1"
        """
        p = {"symbol": symbol}
        if period:
            p["period"] = period
        if start_date:
            p["start_date"] = start_date
        if end_date:
            p["end_date"] = end_date
        if count is not None:
            p["count"] = count
        if fields:
            p["fields"] = self._to_list(fields)
        return self._query_single("/api/v1/quote/capital-flow-range", p)

    # ==================================================================
    # 便捷方法：财务指标与估值
    # ==================================================================

    def get_solvency_leverage(self, symbols, start_date=None, end_date=None, fields=None):
        """偿债与杠杆指标（每股净资产/资产负债率/权益乘数等）。"""
        return self._query_single(
            "/api/v1/stock_fnd/solvency-leverage-metrics",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    def get_tech_indicators(self, symbols, start_date=None, end_date=None, fields=None):
        """标准技术指标（MA5/10/20/60、KDJ、DMI等）。"""
        return self._query_single(
            "/api/v1/stock/tech-indicators",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    def get_yield_factor(self, symbols, start_date=None, end_date=None, fields=None):
        """收益因子（收益率均值/标准差等）。"""
        return self._query_single(
            "/api/v1/stock_fnd/yield-factor",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    def get_style_classification(self, symbols, start_date=None, end_date=None, fields=None):
        """股票风格分类（市值规模/成长价值风格标签）。"""
        return self._query_single(
            "/api/v1/stock_fnd/style-classification",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    def get_specialty_metrics_period(self, symbols, start_date=None, end_date=None, fields=None):
        """金融企业特色财务指标 — 区间（成本收入比/净息差等）。"""
        return self._query_single(
            "/api/v1/stock_fnd/specialty-metrics-period",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    def get_specialty_metrics_point(self, symbols, start_date=None, end_date=None, fields=None):
        """金融企业特色财务指标 — 时点（内含价值/风险贴现率等）。"""
        return self._query_single(
            "/api/v1/stock_fnd/specialty-metrics-point",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    def get_index_financial_ratios(self, symbols, start_date=None, end_date=None, fields=None):
        """指数财务指标（EPS/BPS/ROE/ROA/流动比率等）。"""
        return self._query_single(
            "/api/v1/index_fnd/index-fnd-financial-ratios",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    def get_index_financial_ratios_single(self, symbols, start_date=None, end_date=None, fields=None):
        """指数财务指标 — 单季。"""
        return self._query_single(
            "/api/v1/index_fnd/index-fnd-financial-ratios-single",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    # ==================================================================
    # 便捷方法：主营构成
    # ==================================================================

    def get_main_business_industry(self, symbols, start_date=None, end_date=None, fields=None):
        """主营业务构成 — 按行业（A股）。"""
        return self._query_single(
            "/api/v1/stock_fnd/main-business-industry",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    def get_main_business_product(self, symbols, start_date=None, end_date=None, fields=None):
        """主营业务构成 — 按产品（A股/港股）。"""
        return self._query_single(
            "/api/v1/stock_fnd/main-business-product",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    def get_main_business_business(self, symbols, start_date=None, end_date=None, fields=None):
        """主营业务构成 — 按业务板块（港股/美股）。"""
        return self._query_single(
            "/api/v1/stock_fnd/main-business-business",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    # ==================================================================
    # 便捷方法：股东股本
    # ==================================================================

    def get_shareholder_list(self, symbols, start_date=None, end_date=None, fields=None):
        """前十大股东名单（A股/港股/美股，季频）。"""
        return self._query_single(
            "/api/v1/stock_fnd/shareholder-list",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    def get_holder_count(self, symbols, start_date=None, end_date=None, fields=None):
        """股东户数（A股）。"""
        return self._query_single(
            "/api/v1/stock_fnd/holder-count",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    def get_holding_stats(self, symbols, start_date=None, end_date=None, fields=None):
        """机构持股统计（A股，季频）。"""
        return self._query_single(
            "/api/v1/stock_fnd/holding-stats",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    def get_change_plan(self, symbols, start_date=None, end_date=None, fields=None):
        """股东增减持计划（A股）。"""
        return self._query_single(
            "/api/v1/stock/change-plan",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    def get_shareholder_commitment(self, symbols, start_date=None, end_date=None, fields=None):
        """股东承诺及履行情况（A股）。"""
        return self._query_single(
            "/api/v1/stock_fnd/shareholder-commitment",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    # ==================================================================
    # 便捷方法：分红融资
    # ==================================================================

    def get_dividend_record(self, symbols, start_date=None, end_date=None, fields=None):
        """除权除息记录（A股/港股/美股）。"""
        return self._query_single(
            "/api/v1/stock_fnd/dividend-record",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    def get_dividend_details(self, symbols, start_date=None, end_date=None, fields=None):
        """分红方案明细（A股/港股/美股）。"""
        return self._query_single(
            "/api/v1/stock_fnd/dividend-details",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    def get_seo_placement(self, symbols, start_date=None, end_date=None, fields=None):
        """增发配股明细（A股）。"""
        return self._query_single(
            "/api/v1/stock_fnd/seo-placement-details",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    def get_prelim_acc(self, symbols, start_date=None, end_date=None, fields=None):
        """业绩快报 — 累计（A股）。"""
        return self._query_single(
            "/api/v1/stock_fnd/prelim-acc",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    # ==================================================================
    # 便捷方法：特色专题
    # ==================================================================

    def get_margin_trading(self, symbols, start_date=None, end_date=None, fields=None):
        """融资融券交易明细（A股）。"""
        return self._query_single(
            "/api/v1/stock/market-detail",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    def get_northbound_trade(self, symbols, start_date=None, end_date=None, fields=None):
        """沪深港通交易统计（北向资金净买入）。"""
        return self._query_single(
            "/api/v1/stock/sc-trade",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    def get_northbound_top10(self, symbols, start_date=None, end_date=None, fields=None):
        """沪深港通十大成交股。"""
        return self._query_single(
            "/api/v1/stock/sc-activitie",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    def get_abnormal_trading(self, symbols, start_date=None, end_date=None, fields=None):
        """龙虎榜（交易异动信息）。"""
        return self._query_single(
            "/api/v1/stock/tra-variant",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    # ==================================================================
    # 便捷方法：板块与指数
    # ==================================================================

    def get_plate_list(self, plate_type=None):
        """板块列表查询。

        Args:
            plate_type: 板块类型筛选，如 "行业板块"/"概念板块"
        """
        p = {}
        if plate_type:
            p["plate_type"] = plate_type
        return self._query_single("/api/v1/sector/plate-list", p)

    def get_sector_valuation(self, symbols, start_date=None, end_date=None, fields=None):
        """板块估值指标（市值/股息率/PE/PB等）。"""
        return self._query_single(
            "/api/v1/sector/sector-valuation",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    def get_sector_financial_point(self, symbols, start_date=None, end_date=None, fields=None):
        """板块财务时点指标（每股净资产/资产负债率等）。"""
        return self._query_single(
            "/api/v1/sector/sector-financial-point",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    def get_sector_financial_quarterly(self, symbols, start_date=None, end_date=None, fields=None):
        """板块财务指标 — 单季（营收/净利润/ROE等）。"""
        return self._query_single(
            "/api/v1/sector/sector-financial-quarterly",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    def get_sector_capital_flow(self, symbols, start_date=None, end_date=None, fields=None):
        """板块融资融券统计。"""
        return self._query_single(
            "/api/v1/sector/sector-capital-flow",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    def get_index_constituents(self, symbols, fields=None):
        """指数成分股及权重。"""
        return self._query_single(
            "/api/v1/index_fnd/index-constituents-list-weight",
            self._symbols_params(symbols, fields=fields),
        )

    def get_stock_belonged_sectors(self, symbols, fields=None):
        """股票所属板块查询。"""
        return self._query_single(
            "/api/v1/stock/component-list-belonged",
            self._symbols_params(symbols, fields=fields),
        )

    def get_stock_belonged_indices(self, symbols, fields=None):
        """股票对应指数查询。"""
        return self._query_single(
            "/api/v1/stock/stock-index-constituents-list",
            self._symbols_params(symbols, fields=fields),
        )

    # ==================================================================
    # 便捷方法：资讯与研报
    # ==================================================================

    def get_news_search(self, query, limit=None):
        """全网新闻搜索。

        Args:
            query: 搜索关键词/问题
            limit: 返回条数
        """
        p = {"input_text": query}
        if limit is not None:
            p["limit"] = limit
        return self._query_single("/api/v1/info/news-global-search", p)

    def get_news_by_symbols(self, symbols, start_date, end_date,
                            confidence=None, size=None, key_phrase=None,
                            tag_keys=None, filter_cls_list=None, fields=None):
        """按标的查询财经资讯。

        Args:
            symbols: 标的代码
            start_date/end_date: 必填，"yyyy-MM-dd HH:mm:ss"
            confidence: 置信度筛选
            size: 返回条数
            key_phrase: 关键词筛选
        """
        p = self._symbols_params(symbols, start_date, end_date, fields)
        if confidence is not None:
            p["confidence"] = confidence
        if size is not None:
            p["size"] = size
        if key_phrase:
            p["key_phrase"] = key_phrase
        if tag_keys:
            p["tag_keys"] = self._to_list(tag_keys)
        if filter_cls_list:
            p["filter_cls_list"] = self._to_list(filter_cls_list)
        return self._query_single("/api/v1/info/news-by-symbols", p)

    def get_announcements(self, symbols, start_date=None, end_date=None,
                          feed_id=None, limit=None, fields=None):
        """公司公告查询（A股/港股）。"""
        p = self._symbols_params(symbols, start_date, end_date, fields)
        if feed_id:
            p["feed_id"] = feed_id
        if limit is not None:
            p["limit"] = limit
        return self._query_single("/api/v1/info/announcements", p)

    def get_research_reports(self, symbol, start=None, limit=None, fields=None):
        """研究报告查询（A股）。

        Args:
            symbol: 单个标的代码（str）
        """
        p = {"symbol": symbol}
        if start is not None:
            p["start"] = start
        if limit is not None:
            p["limit"] = limit
        if fields:
            p["fields"] = self._to_list(fields)
        return self._query_single("/api/v1/info/research-reports", p)

    # ==================================================================
    # 便捷方法：宏观与行业
    # ==================================================================

    def get_macro_china(self, query):
        """中国宏观指标（GDP/CPI/PMI/M2/社融等）。

        底层 API 每次仅支持查询单个指标，如需一次查询多个指标请使用
        ``get_macro_china_batch`` 或专用方法 ``get_cpi`` / ``get_pmi`` / ``get_ppi``。

        Args:
            query: 自然语言查询，如 "近三年CPI月度数据"

        Returns:
            dict: V2 响应，results 中为命名时间序列列表，每项含
                  ``meta.name``、``meta.unit`` 与 ``data``（时间→值映射）
        """
        return self._query_single("/api/v1/agent/macro-china", {"input_text": query})

    def get_cpi(self, period="monthly", years=3):
        """查询中国 CPI（居民消费价格指数）。

        Args:
            period: 数据频率，可选 "monthly"（月度）/ "quarterly"（季度）/ "yearly"（年度），
                    默认 "monthly"
            years: 查询最近多少年的数据，默认 3

        Returns:
            dict: V2 响应，results 中为 CPI 时间序列
        """
        freq_label = {"monthly": "月度", "quarterly": "季度", "yearly": "年度"}.get(
            period, "月度"
        )
        query = f"近{years}年中国CPI同比{freq_label}数据"
        return self.get_macro_china(query)

    def get_pmi(self, category="manufacturing", years=3):
        """查询中国 PMI（采购经理人指数）。

        Args:
            category: 指标类别，可选：
                      "manufacturing" — 制造业PMI（默认）
                      "non_manufacturing" — 非制造业PMI
                      "composite" — 综合PMI
            years: 查询最近多少年的数据，默认 3

        Returns:
            dict: V2 响应，results 中为 PMI 时间序列
        """
        cat_label = {
            "manufacturing": "制造业PMI",
            "non_manufacturing": "非制造业PMI",
            "composite": "综合PMI",
        }.get(category, "制造业PMI")
        query = f"近{years}年中国{cat_label}月度数据"
        return self.get_macro_china(query)

    def get_ppi(self, period="monthly", years=3):
        """查询中国 PPI（工业生产者出厂价格指数）。

        Args:
            period: 数据频率，可选 "monthly"（月度）/ "yearly"（年度），默认 "monthly"
            years: 查询最近多少年的数据，默认 3

        Returns:
            dict: V2 响应，results 中为 PPI 时间序列
        """
        freq_label = {"monthly": "月度", "yearly": "年度"}.get(period, "月度")
        query = f"近{years}年中国PPI同比{freq_label}数据"
        return self.get_macro_china(query)

    def get_macro_china_batch(self, queries):
        """批量查询多个中国宏观经济指标（并发执行）。

        底层 API 每次只接受单个指标查询，本方法将多个查询包装为批量请求并发执行，
        适合同时获取 CPI、PMI、PPI 等多个指标数据。

        Args:
            queries: 查询列表，每项可以是：
                     - str: 自然语言查询，如 "近三年CPI月度数据"
                     - dict: {"query": "...", "label": "可选标签"}

        Returns:
            dict: {total, success, failed, results: [{ok, label, data, ...}, ...]}

        Example::

            client.get_macro_china_batch([
                {"query": "近3年CPI同比月度数据", "label": "CPI"},
                {"query": "近3年PMI月度数据", "label": "PMI"},
                {"query": "近3年PPI同比月度数据", "label": "PPI"},
            ])
        """
        if not queries:
            raise FinancialDataError("queries 不能为空", code="PARSE_ERROR")

        requests_list = []
        for item in queries:
            if isinstance(item, str):
                requests_list.append({
                    "url": "/api/v1/agent/macro-china",
                    "params": {"input_text": item},
                })
            elif isinstance(item, dict):
                entry = {
                    "url": "/api/v1/agent/macro-china",
                    "params": {"input_text": item["query"]},
                }
                if item.get("label"):
                    entry["label"] = item["label"]
                requests_list.append(entry)
            else:
                raise FinancialDataError(
                    f"queries 中每项须为 str 或 dict，当前类型: {type(item).__name__}",
                    code="PARSE_ERROR",
                )

        return self.query(requests_list)

    def get_cpi_pmi_ppi(self, years=3):
        """一次性获取 CPI、PMI、PPI 三大宏观指标（并发查询）。

        Args:
            years: 查询最近多少年的数据，默认 3

        Returns:
            dict: {total, success, failed, results: [...]}
                  每项 result 含 label（"CPI"/"PMI"/"PPI"）及对应的时间序列数据
        """
        return self.get_macro_china_batch([
            {"query": f"近{years}年中国CPI同比月度数据", "label": "CPI"},
            {"query": f"近{years}年中国制造业PMI月度数据", "label": "PMI"},
            {"query": f"近{years}年中国PPI同比月度数据", "label": "PPI"},
        ])

    @staticmethod
    def parse_macro_timeseries(api_response):
        """解析宏观指标 API 返回的时间序列数据为结构化列表。

        将 ``{meta: {name, unit}, data: {时间: 值}}`` 格式转换为按时间升序排列的
        ``[{date, value, name, unit}, ...]`` 列表，方便后续处理和展示。

        Args:
            api_response: ``get_macro_china`` / ``get_cpi`` 等方法的原始返回值

        Returns:
            list[dict]: 解析后的指标列表，每个元素为::

                {
                    "name": "CPI:同比:月",
                    "unit": "%",
                    "records": [
                        {"date": "2024-01-31", "value": 0.8},
                        {"date": "2024-02-29", "value": 0.7},
                        ...
                    ]
                }

            如果输入数据为空或格式不匹配，返回空列表。
        """
        if not isinstance(api_response, dict):
            return []

        results = api_response.get("results", [])
        if not isinstance(results, list):
            return []

        parsed = []
        for series in results:
            if not isinstance(series, dict):
                continue
            meta = series.get("meta", {})
            data = series.get("data", {})
            if not isinstance(data, dict):
                continue

            indicator_name = meta.get("name", "未知指标") if isinstance(meta, dict) else "未知指标"
            indicator_unit = meta.get("unit", "") if isinstance(meta, dict) else ""

            records = []
            for date_str, value in data.items():
                normalized_date = date_str.split(" ")[0] if " " in date_str else date_str
                records.append({"date": normalized_date, "value": value})

            records.sort(key=lambda record: record["date"])

            parsed.append({
                "name": indicator_name,
                "unit": indicator_unit,
                "records": records,
            })

        return parsed

    def get_macro_global(self, query):
        """全球宏观指标（各国GDP/CPI/央行利率/大宗商品/汇率等）。

        底层 API 每次仅支持查询单个国家/地区的单个指标，如需一次查询多个指标
        请使用 ``get_macro_global_batch`` 或专用方法如 ``get_vix`` / ``get_gold_price`` 等。

        Args:
            query: 自然语言查询，如 "美国近两年CPI"

        Returns:
            dict: V2 响应，results 中为命名时间序列列表，每项含
                  ``meta.name``、``meta.unit`` 与 ``data``（时间→值映射）
        """
        return self._query_single("/api/v1/agent/macro-global", {"input_text": query})

    def get_vix(self, years=3):
        """查询 VIX 恐慌指数（CBOE 波动率指数）。

        Args:
            years: 查询最近多少年的数据，默认 3

        Returns:
            dict: V2 响应，results 中为 VIX 时间序列
        """
        return self.get_macro_global(f"近{years}年VIX恐慌指数数据")

    def get_gold_price(self, years=3):
        """查询国际黄金价格（伦敦金现）。

        Args:
            years: 查询最近多少年的数据，默认 3

        Returns:
            dict: V2 响应，results 中为黄金价格时间序列
        """
        return self.get_macro_global(f"近{years}年国际黄金现货价格数据")

    def get_copper_price(self, years=3):
        """查询国际铜期货价格（LME 铜）。

        Args:
            years: 查询最近多少年的数据，默认 3

        Returns:
            dict: V2 响应，results 中为铜价格时间序列
        """
        return self.get_macro_global(f"近{years}年LME铜期货价格数据")

    def get_dxy(self, years=3):
        """查询美元指数（DXY）。

        Args:
            years: 查询最近多少年的数据，默认 3

        Returns:
            dict: V2 响应，results 中为美元指数时间序列
        """
        return self.get_macro_global(f"近{years}年美元指数DXY数据")

    def get_brent_oil(self, years=3):
        """查询布伦特原油期货价格。

        Args:
            years: 查询最近多少年的数据，默认 3

        Returns:
            dict: V2 响应，results 中为布伦特原油价格时间序列
        """
        return self.get_macro_global(f"近{years}年布伦特原油期货价格数据")

    def get_wti_oil(self, years=3):
        """查询 WTI 原油期货价格。

        Args:
            years: 查询最近多少年的数据，默认 3

        Returns:
            dict: V2 响应，results 中为 WTI 原油价格时间序列
        """
        return self.get_macro_global(f"近{years}年WTI原油期货价格数据")

    def get_usdcnh(self, years=3):
        """查询美元兑离岸人民币汇率（USDCNH）。

        Args:
            years: 查询最近多少年的数据，默认 3

        Returns:
            dict: V2 响应，results 中为 USDCNH 汇率时间序列
        """
        return self.get_macro_global(f"近{years}年美元兑离岸人民币汇率数据")

    def get_hsi(self, years=3):
        """查询恒生指数（HSI）行情数据。

        Args:
            years: 查询最近多少年的数据，默认 3

        Returns:
            dict: V2 响应，results 中为恒生指数时间序列
        """
        return self.get_macro_global(f"近{years}年恒生指数行情数据")

    def get_macro_global_batch(self, queries):
        """批量查询多个全球宏观指标（并发执行）。

        底层 API 每次只接受单个指标查询，本方法将多个查询包装为批量请求并发执行，
        适合同时获取 VIX、黄金、原油等多个指标数据。

        Args:
            queries: 查询列表，每项可以是：
                     - str: 自然语言查询，如 "近三年VIX恐慌指数"
                     - dict: {"query": "...", "label": "可选标签"}

        Returns:
            dict: {total, success, failed, results: [{ok, label, data, ...}, ...]}

        Example::

            client.get_macro_global_batch([
                {"query": "近3年VIX恐慌指数数据", "label": "VIX"},
                {"query": "近3年国际黄金现货价格数据", "label": "GOLD"},
                {"query": "近3年美元指数DXY数据", "label": "DXY"},
            ])
        """
        if not queries:
            raise FinancialDataError("queries 不能为空", code="PARSE_ERROR")

        requests_list = []
        for item in queries:
            if isinstance(item, str):
                requests_list.append({
                    "url": "/api/v1/agent/macro-global",
                    "params": {"input_text": item},
                })
            elif isinstance(item, dict):
                entry = {
                    "url": "/api/v1/agent/macro-global",
                    "params": {"input_text": item["query"]},
                }
                if item.get("label"):
                    entry["label"] = item["label"]
                requests_list.append(entry)
            else:
                raise FinancialDataError(
                    f"queries 中每项须为 str 或 dict，当前类型: {type(item).__name__}",
                    code="PARSE_ERROR",
                )

        return self.query(requests_list)

    def get_global_market_indicators(self, years=3):
        """一次性获取全球市场核心指标（并发查询）。

        包括 VIX、黄金、铜、美元指数、布伦特原油、WTI原油、USDCNH、恒生指数。

        Args:
            years: 查询最近多少年的数据，默认 3

        Returns:
            dict: {total, success, failed, results: [...]}
                  每项 result 含 label 及对应的时间序列数据
        """
        return self.get_macro_global_batch([
            {"query": f"近{years}年VIX恐慌指数数据", "label": "VIX"},
            {"query": f"近{years}年国际黄金现货价格数据", "label": "GOLD"},
            {"query": f"近{years}年LME铜期货价格数据", "label": "COPPER"},
            {"query": f"近{years}年美元指数DXY数据", "label": "DXY"},
            {"query": f"近{years}年布伦特原油期货价格数据", "label": "BRENT"},
            {"query": f"近{years}年WTI原油期货价格数据", "label": "WTI"},
            {"query": f"近{years}年美元兑离岸人民币汇率数据", "label": "USDCNH"},
            {"query": f"近{years}年恒生指数行情数据", "label": "HSI"},
        ])

    def get_industry_econ(self, query):
        """行业经济指标（产业景气度/产品量价/进出口等）。

        Args:
            query: 自然语言查询，如 "光伏行业产量数据"
        """
        return self._query_single("/api/v1/agent/industry-econ", {"input_text": query})

    # ==================================================================
    # 便捷方法：通用工具
    # ==================================================================

    def get_industry_chain(self, symbol, fields=None):
        """产业链信息查询。

        Args:
            symbol: 产业链代码（str）
        """
        p = {"symbol": symbol}
        if fields:
            p["fields"] = self._to_list(fields)
        return self._query_single("/api/v1/common/industry-chain-tree", p)

    def get_trading_days(self, symbols, start_date=None, end_date=None,
                         count=None, reversed_order=None):
        """交易日查询。"""
        p = {"symbols": self._to_list(symbols)}
        if start_date:
            p["start_date"] = start_date
        if end_date:
            p["end_date"] = end_date
        if count is not None:
            p["count"] = count
        if reversed_order is not None:
            p["reversed_order"] = reversed_order
        return self._query_single("/api/v1/common/trading-day", p)

    def get_trading_state(self, symbols, query_time=None):
        """交易状态查询（是否可交易）。"""
        p = {"symbols": self._to_list(symbols)}
        if query_time:
            p["query_time"] = query_time
        return self._query_single("/api/v1/common/trading-state", p)

    def get_industry_classification(self, symbols, standard, fields=None):
        """股票行业分类查询。

        Args:
            symbols: 标的代码
            standard: 分类标准（必填）
        """
        p = self._symbols_params(symbols, fields=fields)
        p["ind_classification_standard"] = standard
        return self._query_single("/api/v1/stock_fnd/industry-classification", p)

    # ==================================================================
    # 便捷方法：基金
    # ==================================================================

    def get_fund_archive(self, symbols, fields=None):
        """基金档案（规模/策略/费率/风险评级等）。"""
        return self._query_single(
            "/api/v1/fund/fund-archive",
            self._symbols_params(symbols, fields=fields),
        )

    def get_fund_net_value(self, symbols, start_date=None, end_date=None, fields=None):
        """基金净值（单位净值/累计净值/日涨幅等）。"""
        return self._query_single(
            "/api/v1/fund/net-value",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    def get_fund_dividend(self, symbols, start_date=None, end_date=None, fields=None):
        """基金分红历史。"""
        return self._query_single(
            "/api/v1/fund/dividend",
            self._symbols_params(symbols, start_date, end_date, fields),
        )

    def get_fund_company(self, symbol, fields=None):
        """基金管理人信息。

        Args:
            symbol: 单个基金代码（str）
        """
        p = {"symbol": symbol}
        if fields:
            p["fields"] = self._to_list(fields)
        return self._query_single("/api/v1/fund/fund-company-info", p)

    def get_fund_portfolio(self, symbols, fields=None):
        """基金持仓明细（FOF底层基金配置等）。"""
        return self._query_single(
            "/api/v1/fund/fund-portfolio",
            self._symbols_params(symbols, fields=fields),
        )

    # ==================================================================
    # 便捷方法：热门榜单
    # ==================================================================

    def get_hot_plates(self, count=None, rank_field=None,
                       start=None, end=None, reversed_order=None, fields=None):
        """热门板块榜单。

        Args:
            rank_field: 排名字段，如 "实时涨跌幅"/"近一月涨跌幅" 等
        """
        p = {}
        if count is not None:
            p["count"] = count
        if rank_field:
            p["rank_field"] = rank_field
        if start is not None:
            p["start"] = start
        if end is not None:
            p["end"] = end
        if reversed_order is not None:
            p["reversed_order"] = reversed_order
        if fields:
            p["fields"] = self._to_list(fields)
        return self._query_single("/api/v1/altdata/hot-plate-rank", p)

    def get_hot_stocks(self, count=None, start=None, end=None,
                        reversed_order=None, fields=None):
        """热门股票榜单（支付宝散户关注度排名）。"""
        p = {}
        if count is not None:
            p["count"] = count
        if start is not None:
            p["start"] = start
        if end is not None:
            p["end"] = end
        if reversed_order is not None:
            p["reversed_order"] = reversed_order
        if fields:
            p["fields"] = self._to_list(fields)
        return self._query_single("/api/v1/altdata/hot-stock-rank", p)

    def get_tech_patterns(self, symbols, fields=None):
        """技术形态识别：查询个股的程序化技术形态信号（均线排列、创新高等）。"""
        p = {"symbols": self._to_list(symbols)}
        if fields:
            p["fields"] = self._to_list(fields)
        return self._query_single("/api/v1/stock/tech-patterns", p)

    def get_top_gainers_by_plate(self, rank_field='changePercent', count=10):
        """获取涨幅排行板块（通过 hot_plates 按实时涨跌幅排序）。

        Args:
            rank_field: changePercent / changePercentAbs / historyChangePercent1M /
                        historyChangePercent3M / mainInflow / mainInflow1W
            count: 返回条目数，最多200
        """
        return self.get_hot_plates(count=count, rank_field=rank_field, reversed_order=True)

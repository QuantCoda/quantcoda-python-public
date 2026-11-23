"""QuantCoda API 客户端。

    import quantcoda as qc
    qc.set_token("qc_live_你的密钥")            # 或环境变量 QUANTCODA_TOKEN
    df = qc.daily(symbol="600519.SH", start_date="20260101")

数据接口返回 pandas.DataFrame；离线发现方法返回 DataFrame 或契约字典。
公开参数与 https://quantcoda.com/docs 一一对应。
"""
from __future__ import annotations

from copy import deepcopy
from inspect import Parameter, Signature
import os
import re
from typing import Optional

import pandas as pd
import requests

from ._endpoints import ENDPOINTS

DEFAULT_BASE_URL = "https://quantcoda.com"
_ENV_TOKEN = "QUANTCODA_TOKEN"


class QuantCodaError(RuntimeError):
    """API 返回错误。message 为服务端中文说明，status 为 HTTP 状态码。"""

    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


class RateLimitError(QuantCodaError):
    """超出限速（429）。retry_after 为建议等待秒数（突发超限时有值）。"""

    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message, status=429)
        self.retry_after = retry_after


class QuantCoda:
    """API 客户端。每个数据接口都是同名方法：qc.daily(...) / qc.income(...) 等。"""

    def __init__(self, token: str | None = None,
                 base_url: str = DEFAULT_BASE_URL, timeout: float = 30):
        token = token or os.environ.get(_ENV_TOKEN, "")
        if not token:
            raise ValueError(
                f"缺少 API Key：传入 token 参数或设置环境变量 {_ENV_TOKEN}。"
                f"免费获取：{DEFAULT_BASE_URL}/register"
            )
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers["X-API-Key"] = token

    def query(self, path: str, **params) -> pd.DataFrame:
        """按原始路径调用任意端点（named 方法覆盖不到时的逃生口）。"""
        clean = {k: v for k, v in params.items() if v is not None}
        resp = self._session.get(self._base_url + path, params=clean,
                                 timeout=self._timeout)
        if resp.status_code == 429:
            retry = resp.headers.get("Retry-After")
            detail = _detail(resp)
            raise RateLimitError(detail, int(retry) if retry else None)
        if resp.status_code != 200:
            raise QuantCodaError(_detail(resp), resp.status_code)
        return pd.DataFrame(resp.json())

    def search(self, query: str, limit: int = 20) -> pd.DataFrame:
        """离线检索接口；不会发送 HTTP 请求。"""
        return search(query, limit=limit)

    def interface_info(self, name: str) -> dict:
        """离线读取接口详情；支持接口 ID、SDK 方法、路径和别名。"""
        return interface_info(name)

    def list_categories(self) -> pd.DataFrame:
        """离线列出接口分类；不会发送 HTTP 请求。"""
        return list_categories()

    def __getattr__(self, name: str):
        meta = ENDPOINTS.get(name)
        if meta is None:
            raise AttributeError(
                f"QuantCoda 没有接口 {name!r}，可用接口见 quantcoda.endpoints()")

        def _call(**params) -> pd.DataFrame:
            contract_params = meta.get("params", [])
            if contract_params:
                allowed = {param["name"] for param in contract_params}
                unexpected = sorted(set(params) - allowed)
                if unexpected:
                    raise TypeError(
                        f"{name}() got unexpected parameter(s): {', '.join(unexpected)}"
                    )
                missing = [
                    param["name"] for param in contract_params
                    if param.get("required") and params.get(param["name"]) is None
                ]
                if missing:
                    raise TypeError(
                        f"{name}() missing required parameter(s): {', '.join(missing)}"
                    )
            return self.query(meta["path"], **params)

        _call.__name__ = name
        param_names = [param["name"] for param in meta.get("params", [])]
        field_names = [field["name"] for field in meta.get("fields", [])]
        _call.__doc__ = (
            f"{meta['summary']}（GET {meta['path']}）\n\n"
            f"Parameters: {', '.join(param_names) or '(none)'}\n"
            f"Response fields: {', '.join(field_names)}"
        )
        if meta.get("params"):
            signature = []
            for param in meta["params"]:
                scalar = int if param.get("type") == "integer" else str
                # ``type | None`` is only executable from Python 3.10 onward;
                # the SDK supports Python 3.9, so build the runtime signature
                # with typing.Optional instead.
                annotation = scalar if param.get("required") else Optional[scalar]
                default = (
                    Parameter.empty if param.get("required")
                    else param.get("default")
                )
                signature.append(Parameter(
                    param["name"], Parameter.KEYWORD_ONLY,
                    annotation=annotation, default=default,
                ))
            _call.__signature__ = Signature(signature, return_annotation=pd.DataFrame)
        return _call

    def __dir__(self):
        return sorted(set(super().__dir__()) | set(ENDPOINTS))


def _detail(resp) -> str:
    try:
        return resp.json().get("detail") or resp.json().get("error") or resp.text[:200]
    except Exception:
        return f"HTTP {resp.status_code}"


def endpoints() -> pd.DataFrame:
    """全部可用接口一览，含套餐、参数和返回字段。"""
    return pd.DataFrame(
        [{
            "method": k,
            "http_method": v.get("http_method", "GET"),
            "path": v["path"],
            "summary": v["summary"],
            "group": v.get("group", ""),
            "tier": v.get("tier", ""),
            "parameters": [param["name"] for param in v.get("params", [])],
            "response_fields": [field["name"] for field in v.get("fields", [])],
        }
         for k, v in ENDPOINTS.items()]
    )


def endpoint_schema(name: str) -> dict:
    """返回一个 SDK 方法的完整参数与响应字段契约副本。"""
    if name not in ENDPOINTS:
        raise KeyError(f"未知 QuantCoda 方法: {name}")
    return deepcopy(ENDPOINTS[name])


_SEARCH_COLUMNS = [
    "interface_id", "method", "path", "summary", "summary_en",
    "category", "category_en", "tier", "score", "matched_terms",
    "unmatched_terms",
]


def _normalize_search_text(value: object) -> str:
    text = str(value or "").casefold()
    return " ".join(part for part in re.split(r"[^\w\u3400-\u9fff]+", text) if part)


def _searchable_text(meta: dict) -> tuple[str, str, str]:
    identity = _normalize_search_text(" ".join([
        meta.get("interface_id", ""), meta.get("method", ""),
        meta.get("path", ""), *meta.get("aliases", []),
    ]))
    headline = _normalize_search_text(" ".join([
        meta.get("summary", ""), meta.get("summary_en", ""),
        meta.get("group", ""), meta.get("group_en", ""),
    ]))
    details = [meta.get("description", ""), meta.get("description_en", "")]
    for item in [*meta.get("params", []), *meta.get("fields", [])]:
        details.extend([item.get("name", ""), item.get("desc", "")])
    return identity, headline, _normalize_search_text(" ".join(details))


def search(query: str, limit: int = 20) -> pd.DataFrame:
    """Search bundled endpoint metadata without an API key or network access.

    Results are deterministic. Partial matches remain visible, while
    ``unmatched_terms`` makes unsupported parts of a query explicit to people
    and AI agents instead of silently claiming broader data coverage.
    """
    normalized = _normalize_search_text(query)
    if not normalized:
        raise ValueError("query 不能为空")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise ValueError("limit 必须是正整数")

    terms = list(dict.fromkeys(normalized.split()))
    raw_key = str(query).strip().casefold()
    rows = []
    for order, (method, meta) in enumerate(ENDPOINTS.items()):
        identity, headline, details = _searchable_text(meta)
        exact_keys = {
            str(value).casefold()
            for value in [
                meta.get("interface_id"), method, meta.get("path"),
                *meta.get("aliases", []),
            ]
            if value
        }
        matched = []
        score = 10_000 if raw_key in exact_keys else 0
        for term in terms:
            if term in identity:
                score += 100
                matched.append(term)
            elif term in headline:
                score += 50
                matched.append(term)
            elif term in details:
                score += 10
                matched.append(term)
        if not matched and not score:
            continue
        unmatched = [term for term in terms if term not in matched]
        rows.append({
            "interface_id": meta["interface_id"],
            "method": method,
            "path": meta["path"],
            "summary": meta["summary"],
            "summary_en": meta.get("summary_en", ""),
            "category": meta.get("group", ""),
            "category_en": meta.get("group_en", ""),
            "tier": meta.get("tier", ""),
            "score": score,
            "matched_terms": matched,
            "unmatched_terms": unmatched,
            "_matched_count": len(matched),
            "_order": order,
        })

    rows.sort(key=lambda item: (
        -item["_matched_count"], -item["score"], item["_order"],
    ))
    for item in rows:
        item.pop("_matched_count")
        item.pop("_order")
    return pd.DataFrame(rows[:limit], columns=_SEARCH_COLUMNS)


def interface_info(name: str) -> dict:
    """Return a defensive copy of bundled metadata for one interface."""
    key = str(name or "").strip().casefold()
    if not key:
        raise ValueError("name 不能为空")
    matches = []
    for method, meta in ENDPOINTS.items():
        keys = {
            str(value).casefold()
            for value in [
                meta.get("interface_id"), method, meta.get("path"),
                *meta.get("aliases", []),
            ]
            if value
        }
        if key in keys:
            matches.append(meta)
    if not matches:
        raise KeyError(f"未知 QuantCoda 接口: {name}")
    if len(matches) > 1:
        raise ValueError(f"接口标识不唯一: {name}")
    return deepcopy(matches[0])


def list_categories() -> pd.DataFrame:
    """List bundled interface categories in canonical contract order."""
    categories: dict[tuple[str, str], list[str]] = {}
    for method, meta in ENDPOINTS.items():
        key = (meta.get("group", ""), meta.get("group_en", ""))
        categories.setdefault(key, []).append(method)
    return pd.DataFrame([
        {
            "category": category,
            "category_en": category_en,
            "interface_count": len(methods),
            "methods": list(methods),
        }
        for (category, category_en), methods in categories.items()
    ])

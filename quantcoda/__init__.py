"""QuantCoda —— A 股量化数据 API 官方 Python SDK。

    import quantcoda as qc
    qc.set_token("qc_live_你的密钥")
    df = qc.daily(symbol="600519.SH", start_date="20260101")

文档：https://quantcoda.com/docs
"""
from __future__ import annotations

from ._endpoints import ENDPOINTS
from .client import (DEFAULT_BASE_URL, QuantCoda, QuantCodaError,
                     RateLimitError, endpoint_schema, endpoints,
                     interface_info, list_categories, search)

__version__ = "0.1.5"
__all__ = ["QuantCoda", "QuantCodaError", "RateLimitError",
           "set_token", "endpoints", "endpoint_schema", "search",
           "interface_info", "list_categories", "ENDPOINTS"]

_default_client: QuantCoda | None = None


def set_token(token: str, base_url: str = DEFAULT_BASE_URL) -> QuantCoda:
    """设置默认 Key，之后可直接 qc.daily(...) 调用模块级方法。"""
    global _default_client
    _default_client = QuantCoda(token=token, base_url=base_url)
    return _default_client


def _require_client() -> QuantCoda:
    global _default_client
    if _default_client is None:
        # 未显式 set_token 时尝试环境变量（QuantCoda() 内部处理）
        _default_client = QuantCoda()
    return _default_client


def __getattr__(name: str):
    """模块级转发：qc.daily(...) == qc 默认客户端的 daily(...)。"""
    if name in ENDPOINTS or name == "query":
        return getattr(_require_client(), name)
    raise AttributeError(f"module 'quantcoda' has no attribute {name!r}")


def __dir__():
    return sorted(list(globals()) + list(ENDPOINTS) + ["query"])

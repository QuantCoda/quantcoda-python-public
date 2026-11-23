"""SDK 单测：不触网（mock requests.Session.get）。"""
import inspect
from pathlib import Path
import re

import pandas as pd
import pytest

import quantcoda
from quantcoda import QuantCoda, QuantCodaError, RateLimitError
from quantcoda._endpoints import ENDPOINTS


def test_public_pypi_copy_uses_product_native_language():
    root = Path(__file__).resolve().parents[1]
    public_files = [root / "README.md", root / "pyproject.toml"]
    public_files.extend((root / "quantcoda").glob("*.py"))
    forbidden = ("tu" + "share", "命名" + "对齐", "quant" + "sonar")

    for path in public_files:
        content = path.read_text(encoding="utf-8").casefold()
        for phrase in forbidden:
            assert phrase.casefold() not in content, f"{phrase!r} found in {path.name}"


def test_package_and_runtime_versions_match():
    pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text()
    match = re.search(r'^version = "([^"]+)"$', pyproject, flags=re.MULTILINE)
    assert match and quantcoda.__version__ == match.group(1) == "0.1.5"


def test_pricing_copy_matches_current_pro_and_expert_contract():
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text()

    assert "Pro 开放全部现有标准数据" in readme
    assert "Expert 包含 Pro 全部能力并提供最高 500 次/分钟" in readme
    assert "Starter" not in readme


class FakeResp:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else []
        self.headers = headers or {}
        self.text = str(self._payload)

    def json(self):
        return self._payload


@pytest.fixture
def client(monkeypatch):
    c = QuantCoda(token="qc_live_test")
    c._calls = []

    def fake_get(url, params=None, timeout=None):
        c._calls.append((url, params))
        return c._next_resp

    monkeypatch.setattr(c._session, "get", fake_get)
    return c


def test_requires_token(monkeypatch):
    monkeypatch.delenv("QUANTCODA_TOKEN", raising=False)
    with pytest.raises(ValueError):
        QuantCoda()


def test_env_token(monkeypatch):
    monkeypatch.setenv("QUANTCODA_TOKEN", "qc_live_env")
    assert QuantCoda()._token == "qc_live_env"


def test_daily_returns_dataframe(client):
    client._next_resp = FakeResp(payload=[
        {"symbol": "600519.SH", "trade_date": "20260710", "close": 1204.98},
    ])
    df = client.daily(symbol="600519.SH", start_date="20260101")
    assert isinstance(df, pd.DataFrame)
    assert df.iloc[0]["close"] == 1204.98
    url, params = client._calls[0]
    assert url.endswith("/v1/market/daily")
    assert params == {"symbol": "600519.SH", "start_date": "20260101"}


def test_none_params_dropped(client):
    client._next_resp = FakeResp(payload=[])
    client.daily(symbol="600519.SH", start_date=None)
    assert client._calls[0][1] == {"symbol": "600519.SH"}


def test_rate_limit_error(client):
    client._next_resp = FakeResp(429, {"detail": "超出突发限速"}, {"Retry-After": "12"})
    with pytest.raises(RateLimitError) as e:
        client.daily(symbol="600519.SH")
    assert e.value.retry_after == 12
    assert "超出" in str(e.value)


def test_api_error(client):
    client._next_resp = FakeResp(422, {"detail": "证券代码需带交易所后缀"})
    with pytest.raises(QuantCodaError) as e:
        client.daily(symbol="600519")
    assert e.value.status == 422


def test_unknown_endpoint_raises(client):
    with pytest.raises(AttributeError):
        client.no_such_endpoint


def test_all_endpoints_are_callable(client):
    client._next_resp = FakeResp(payload=[])
    for name in ENDPOINTS:
        assert callable(getattr(client, name)), name


def test_all_endpoint_contracts_have_unique_params_and_fields():
    assert len(ENDPOINTS) == 45
    assert len({meta["interface_id"] for meta in ENDPOINTS.values()}) == 45
    for name, meta in ENDPOINTS.items():
        assert {
            "interface_id", "method", "sdk_method", "mcp_tool", "aliases",
            "path", "http_method", "summary", "summary_en", "description",
            "description_en", "group", "group_en", "tier", "params", "fields",
        } <= set(meta), name
        assert meta["method"] == meta["sdk_method"] == meta["mcp_tool"] == name
        assert meta["http_method"] == "GET", name
        params = [param["name"] for param in meta["params"]]
        fields = [field["name"] for field in meta["fields"]]
        assert len(params) == len(set(params)), name
        assert len(fields) == len(set(fields)), name
        assert fields, name
        assert meta["tier"] in {"free", "pro"}, name


def test_dynamic_method_signatures_match_contract(client):
    for name, meta in ENDPOINTS.items():
        signature = inspect.signature(getattr(client, name))
        assert list(signature.parameters) == [p["name"] for p in meta["params"]], name
        required = {
            p.name for p in signature.parameters.values()
            if p.default is inspect.Parameter.empty
        }
        assert required == {
            p["name"] for p in meta["params"] if p["required"]
        }, name
        assert {
            p.name: p.default for p in signature.parameters.values()
            if p.default is not inspect.Parameter.empty
        } == {
            p["name"]: p.get("default") for p in meta["params"]
            if not p["required"]
        }, name


def test_sdk_rejects_unknown_and_missing_required_params(client):
    client._next_resp = FakeResp(payload=[])
    with pytest.raises(TypeError, match="unexpected"):
        client.daily(index_code="000300.SH")
    with pytest.raises(TypeError, match="source"):
        client.news_flash()
    assert not client._calls


def test_endpoint_schema_is_a_defensive_copy():
    schema = quantcoda.endpoint_schema("daily")
    schema["params"].clear()
    assert ENDPOINTS["daily"]["params"]
    with pytest.raises(KeyError):
        quantcoda.endpoint_schema("missing")


def test_module_level_endpoints_listing():
    df = quantcoda.endpoints()
    assert len(df) == len(ENDPOINTS) >= 38
    assert {
        "method", "http_method", "path", "summary", "group", "tier",
        "parameters", "response_fields",
    } <= set(df.columns)


def test_offline_search_ranks_exact_interface_id_first():
    results = quantcoda.search("market_daily")
    assert results.iloc[0]["interface_id"] == "market_daily"
    assert results.iloc[0]["method"] == "daily"
    assert results.iloc[0]["unmatched_terms"] == []


def test_offline_search_exposes_partial_query_coverage():
    results = quantcoda.search("可转债 实时行情")
    realtime = results[results["interface_id"] == "market_realtime"].iloc[0]
    assert realtime["matched_terms"] == ["实时行情"]
    assert realtime["unmatched_terms"] == ["可转债"]


def test_offline_search_is_deterministic_and_validates_input():
    first = quantcoda.search("daily", limit=3)
    second = quantcoda.search("daily", limit=3)
    pd.testing.assert_frame_equal(first, second)
    with pytest.raises(ValueError, match="query"):
        quantcoda.search("  ")
    with pytest.raises(ValueError, match="limit"):
        quantcoda.search("daily", limit=0)


def test_interface_info_accepts_id_method_path_and_alias():
    expected = quantcoda.interface_info("market_daily")
    assert expected["method"] == "daily"
    assert quantcoda.interface_info("daily") == expected
    assert quantcoda.interface_info("market.daily") == expected
    assert quantcoda.interface_info("/v1/market/daily") == expected

    expected["params"].clear()
    assert quantcoda.interface_info("market_daily")["params"]
    with pytest.raises(KeyError):
        quantcoda.interface_info("missing")


def test_list_categories_is_offline_and_complete():
    categories = quantcoda.list_categories()
    assert categories["interface_count"].sum() == len(ENDPOINTS)
    assert "行情数据" in set(categories["category"])
    assert "Market Data" in set(categories["category_en"])


def test_client_offline_discovery_methods_do_not_call_http(client):
    assert client.search("market_daily").iloc[0]["method"] == "daily"
    assert client.interface_info("market_daily")["path"] == "/v1/market/daily"
    assert client.list_categories()["interface_count"].sum() == len(ENDPOINTS)
    assert client._calls == []

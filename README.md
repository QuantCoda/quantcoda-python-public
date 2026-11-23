# QuantCoda Python SDK

[![tests](https://github.com/QuantCoda/quantcoda-python-public/actions/workflows/tests.yml/badge.svg)](https://github.com/QuantCoda/quantcoda-python-public/actions/workflows/tests.yml) [![PyPI](https://img.shields.io/pypi/v/quantcoda)](https://pypi.org/project/quantcoda/)

[官网](https://quantcoda.com/?utm_source=pypi&utm_medium=referral&utm_campaign=python_sdk&utm_content=readme) · [API 文档](https://quantcoda.com/docs?utm_source=pypi&utm_medium=referral&utm_campaign=python_sdk&utm_content=readme) · [免费注册](https://quantcoda.com/register?utm_source=pypi&utm_medium=referral&utm_campaign=python_sdk&utm_content=readme) · [MCP 接入](https://quantcoda.com/docs?utm_source=pypi&utm_medium=referral&utm_campaign=python_sdk&utm_content=readme_mcp)

[QuantCoda](https://quantcoda.com) 官方 Python SDK —— A 股行情、财务、资金流、筹码、龙虎榜，45 个数据接口，一个 API Key 全部拿到。

本仓库是公开源码版。安装正式发行包请使用 PyPI；这里不运行 PyPI 发布工作流。

## 安装

```bash
pip install quantcoda
```

## 快速开始

```python
import quantcoda as qc

qc.set_token("qc_live_你的密钥")   # 免费注册: https://quantcoda.com/register

# 贵州茅台 2026 年以来的日线（返回 pandas.DataFrame）
df = qc.daily(symbol="600519.SH", start_date="20260101")

# 每日指标 / 财务 / 资金流 / 龙虎榜……全部同一姿势
qc.fundamentals(symbol="600519.SH", trade_date="20260710")
qc.income(symbol="600519.SH", period="20251231")
qc.moneyflow(trade_date="20260710")
qc.top_list(trade_date="20260710")

# 指数与外汇
qc.index_daily(symbol="000300.SH", start_date="20260101")
qc.fx_daily(start_date="20260101")

# 实时行情与快讯
qc.realtime(symbol="600519.SH,300750.SZ")
qc.news_flash(source="cls")
```

- Key 也可以放环境变量 `QUANTCODA_TOKEN`，省去 `set_token`
- 全部接口一览：`qc.endpoints()`（方法名、路径、套餐、参数与返回字段）
- 单个接口的完整契约：`qc.endpoint_schema("daily")`
- 参数与返回字段和 [在线文档](https://quantcoda.com/docs) 一一对应；日期统一 `YYYYMMDD`，证券代码带交易所后缀（`600519.SH`）

## 离线接口检索

接口元数据随 SDK 安装包分发，不需要 API Key，也不会发送网络请求：

```python
import quantcoda as qc

matches = qc.search("可转债 实时行情")
info = qc.interface_info("market_daily")
categories = qc.list_categories()
```

使用已有客户端时也可以调用同名方法：

```python
client.search("可转债 实时行情")
client.interface_info("market_daily")
client.list_categories()
```

`search()` 返回确定性排序的 DataFrame；`matched_terms` 和 `unmatched_terms`
会明确区分命中的能力与当前元数据没有声明的查询条件，避免人或 AI Agent
把部分匹配误认为完整数据覆盖。`interface_info()` 同时接受接口 ID、SDK 方法名、
点分别名和 REST 路径，例如 `market_daily`、`daily`、`market.daily` 和
`/v1/market/daily`。

## 错误处理

```python
from quantcoda import QuantCodaError, RateLimitError

try:
    df = qc.daily(symbol="600519.SH")
except RateLimitError as e:      # 超出限速（429）
    print(e, "建议等待:", e.retry_after, "秒")
except QuantCodaError as e:     # 其他错误，中文说明
    print(e.status, e)
```

## 多账号 / 自定义

```python
from quantcoda import QuantCoda

client = QuantCoda(token="qc_live_另一把密钥", timeout=60)
df = client.daily(symbol="000001.SZ", start_date="20260101")
```

## 定价

免费版 100 次/天，无需信用卡。Pro 开放全部现有标准数据；Expert 包含 Pro 全部能力并提供最高 500 次/分钟的请求频率 —— [定价页](https://quantcoda.com/pricing)。

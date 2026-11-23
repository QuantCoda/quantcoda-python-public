# Changelog

## 0.1.5

- Bundle bilingual endpoint-discovery metadata with the installed package.
- Add offline `search()`, `interface_info()` and `list_categories()` helpers at both module and client level.
- Add stable path-derived interface IDs such as `market_daily`, with deterministic partial-match reporting for people and AI agents.

## 0.1.4

- Include HTTP methods and effective parameter defaults in the generated endpoint contract.
- Expose those defaults through inspectable SDK method signatures and `endpoint_schema()`.
- Update Expert plan copy to describe the currently available higher-throughput benefit.

## 0.1.1

- Synchronize all 45 SDK methods with the QuantCoda REST, MCP, Skill and documentation contract.
- Expose parameter names, requiredness, types, plan tiers and response fields through `endpoint_schema()`.
- Reject unknown parameters and missing required parameters before sending a request.
- Preserve Python 3.9 through 3.13 compatibility for generated method signatures.

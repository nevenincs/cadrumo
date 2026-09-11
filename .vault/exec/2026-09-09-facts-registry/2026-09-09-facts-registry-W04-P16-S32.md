---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:0be99d05894aa32bdf99932db0df904314cd39023a7d84845028dfd76251080a'
step_id: 'S32'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# Delete numeric IVA interpretation but retain persisted enum tokens

## Scope

- `src/cadrumo/domain/invoices/enums.py`

## Changes

- `A` `.vault/audit/2026-09-11-facts-registry-s32-iva-interpretation-retirement-audit.md`
- `M` `.vault/index/facts-registry.index.md`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `M` `src/cadrumo/domain/invoices/tests/test_rate_parity.py`
- `verify:` `uv run ruff check src/cadrumo/domain/invoices/tests/test_rate_parity.py src/cadrumo/domain/invoices/enums.py` -> `pass`
- `verify:` `uv run python -c <direct S32 AST census invocation>` -> `pass`
- `verify:` `uv run python -m compileall -q src/cadrumo/domain/invoices/enums.py src/cadrumo/domain/invoices/tests/test_rate_parity.py` -> `pass`

## Notes

The S32 code deletion predates this checkpoint: commits `b460bd8c41f` and `411f2b22e227` removed the named helpers. `pytest` cannot reach the focused tests because the global fixture requires the absent signed `src/cadrumo/_data/registry/authority/authority.json`; no artifact was fabricated.

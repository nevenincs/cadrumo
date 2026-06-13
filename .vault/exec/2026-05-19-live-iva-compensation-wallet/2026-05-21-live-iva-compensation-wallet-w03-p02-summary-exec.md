---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# `live-iva-compensation-wallet` `W03.P02` summary

Completed the yearly IVA summary forms phase for `W03.P02.S01` through `W03.P02.S03`.

- Modified: `src/aeat/domain/calculations/registry/_bindings.py`
- Modified: `src/aeat/domain/calculations/registry/__init__.py`
- Modified: `src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py`
- Modified: `src/aeat/domain/calculations/registry/test_modelo_390_registry.py`
- Modified: `src/aeat/application/aggregation/_iva_ledger.py`
- Modified: `src/aeat/application/aggregation/test_iva_ledger.py`
- Modified: `src/aeat/application/modelo/test_bucket_aggregation_flow.py`
- Created: `src/aeat/application/calculations/test_binding_prefill.py`
- Modified: `.vault/audit/2026-05-20-live-iva-compensation-wallet-review.md`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`
- Created: `.vault/exec/2026-05-19-live-iva-compensation-wallet/2026-05-21-live-iva-compensation-wallet-w03-p02-s01.md`
- Created: `.vault/exec/2026-05-19-live-iva-compensation-wallet/2026-05-21-live-iva-compensation-wallet-w03-p02-s02.md`
- Created: `.vault/exec/2026-05-19-live-iva-compensation-wallet/2026-05-21-live-iva-compensation-wallet-w03-p02-s03.md`

## Description

The phase hardened Modelo 390 annual IVA reconciliation across four Modelo 303 periods. It added coverage for annual compensation casillas `97` and `662`, blocked concrete pre-classified IVA observations whose category/rate/flow triples are unsupported by the target revision, and added an application-level cross-form test over persisted 303 observations in the encrypted local observation store.

The registry-level coverage now proves annual ledger-derived totals reconcile with 303-sourced annual totals, and the application-level coverage proves Modelo 390 previous-filing prefill consumes the local observation repository rather than only in-memory fixtures.

No live AEAT calls, browser sessions, wallet pulls, form submissions, signing, payment, amendment, or remote mutation paths were run during this phase.

The rolling audit captures the phase issues and mitigations as `WALLET-039`, `WALLET-040`, and `WALLET-041`.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py src/aeat/domain/calculations/registry/test_modelo_390_registry.py src/aeat/core/test_external_constants.py -q` completed with 55 passed.
- `uv run pytest src/aeat/application/modelo/test_bucket_aggregation_flow.py -q` completed with 5 passed.
- `uv run pytest src/aeat/application/aggregation/test_iva_ledger.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py src/aeat/domain/calculations/registry/test_modelo_390_registry.py src/aeat/application/modelo/test_bucket_aggregation_flow.py -q` completed with 60 passed.
- `uv run pytest src/aeat/application/calculations/test_binding_prefill.py src/aeat/application/calculations/test_observations_repository_roundtrip.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py src/aeat/domain/calculations/registry/test_modelo_390_registry.py -q` completed with 36 passed.
- `uv run ruff check src/aeat/application/aggregation/_iva_ledger.py src/aeat/application/aggregation/test_iva_ledger.py src/aeat/application/calculations/test_binding_prefill.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py src/aeat/domain/calculations/registry/test_modelo_390_registry.py src/aeat/core/test_external_constants.py` passed across the focused phase files.
- `git diff --check -- src/aeat/application/aggregation/_iva_ledger.py src/aeat/application/aggregation/test_iva_ledger.py src/aeat/application/calculations/test_binding_prefill.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py src/aeat/domain/calculations/registry/test_modelo_390_registry.py src/aeat/core/test_external_constants.py` passed, with CRLF warnings only on pre-existing line endings.

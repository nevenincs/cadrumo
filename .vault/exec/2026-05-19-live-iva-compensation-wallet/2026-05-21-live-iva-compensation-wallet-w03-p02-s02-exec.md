---
tags: ["#exec", "#live-iva-compensation-wallet"]
date: "2026-05-21"
modified: '2026-05-21'
step_id: "S02"
related:
  - "[[2026-05-19-live-iva-compensation-wallet-plan]]"
---

# `live-iva-compensation-wallet` `W03.P02.S02`

Blocked unsupported IVA ledger regimes from being silently inferred or dropped by Modelo 390 annual binding resolution.

- Modified: `src/aeat/domain/calculations/registry/_bindings.py`
- Modified: `src/aeat/domain/calculations/registry/__init__.py`
- Modified: `src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py`
- Modified: `src/aeat/application/aggregation/_iva_ledger.py`
- Modified: `src/aeat/application/aggregation/test_iva_ledger.py`
- Modified: `.vault/audit/2026-05-20-live-iva-compensation-wallet-review.md`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`

## Description

The generic IVA binding resolver still resolves supported binding selectors with zero when no rows match. The new support boundary distinguishes that valid empty-match case from a concrete pre-classified observation whose category/rate/flow triple no selector on the target revision can consume.

Added `unsupported_ledger_iva_observations` to the registry public surface and wired `aggregate_iva_ledger_candidate_bindings` to fail closed before binding resolution when unsupported observations are present. This prevents a Modelo 390 candidate call from silently dropping represented IVA regimes such as recargo de equivalencia. Modelo 309 remains verified for recargo and intra-community reverse-charge candidates through its explicit bindings.

No live AEAT calls, browser sessions, wallet pulls, form submissions, signing, payment, amendment, or remote mutation paths were run for this step.

The rolling audit records the original gap as `WALLET-040`.

The exact L3 plan row was closed by direct checkbox edit because the current vaultspec step command accepts only duplicate leaf ids such as `S02`.

## Tests

- `uv run pytest src/aeat/application/aggregation/test_iva_ledger.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py -q` completed with 43 passed.
- `uv run pytest src/aeat/application/aggregation/test_iva_ledger.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py src/aeat/domain/calculations/registry/test_modelo_390_registry.py src/aeat/application/modelo/test_bucket_aggregation_flow.py -q` completed with 60 passed.
- `uv run ruff check src/aeat/application/aggregation/_iva_ledger.py src/aeat/application/aggregation/test_iva_ledger.py src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py` passed.
- `git diff --check -- src/aeat/application/aggregation/_iva_ledger.py src/aeat/application/aggregation/test_iva_ledger.py src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py` passed.

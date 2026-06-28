---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# `live-iva-compensation-wallet` `W03.P01` summary

Completed the ledger-to-periodic-IVA calculation trace phase for `W03.P01.S01` through `W03.P01.S03`.

- Modified: `src/aeat/application/aggregation/_iva_ledger.py`
- Modified: `src/aeat/application/aggregation/__init__.py`
- Modified: `src/aeat/application/aggregation/test_iva_ledger.py`
- Modified: `src/aeat/application/modelo/test_bucket_aggregation_flow.py`
- Modified: `.vault/audit/2026-05-20-live-iva-compensation-wallet-review.md`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`
- Created: `.vault/exec/2026-05-19-live-iva-compensation-wallet/2026-05-21-live-iva-compensation-wallet-w03-p01-s01.md`
- Created: `.vault/exec/2026-05-19-live-iva-compensation-wallet/2026-05-21-live-iva-compensation-wallet-w03-p01-s02.md`
- Created: `.vault/exec/2026-05-19-live-iva-compensation-wallet/2026-05-21-live-iva-compensation-wallet-w03-p01-s03.md`

## Description

The phase hardened the path from ledger evidence into Modelo 303 outputs without introducing live AEAT calls or any live submission behavior.

`W03.P01.S01` added a pre-classified IVA candidate boundary for operation evidence that cannot be inferred safely from ordinary domestic bank rows. It covers non-domestic categories, recargo, exemptions, reverse charge, and signed adjustments while rejecting non-declarable sentinel categories before registry binding.

`W03.P01.S02` strengthened Modelo 303 bucket aggregation coverage by asserting registry-backed provenance. Bound ledger casillas now have direct observation provenance, while computed casillas must expose registry formula ids, operand refs, legal refs, and source refs.

`W03.P01.S03` added real-behavior period coverage for positive, negative, zero, and compensation-applied Modelo 303 results from bucket-local ledger rows through calculated revisions.

The rolling audit captures the issues and mitigations as `WALLET-036`, `WALLET-037`, and `WALLET-038`.

## Tests

- `uv run pytest src/aeat/application/aggregation/test_iva_ledger.py -q` completed with 23 passed.
- `uv run pytest src/aeat/application/aggregation/test_iva_ledger.py src/aeat/application/aggregation/test_oss_ioss.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py -q` completed with 58 passed.
- `uv run pytest src/aeat/application/modelo/test_bucket_aggregation_flow.py -q` completed with 5 passed.
- `uv run pytest src/aeat/application/aggregation/test_iva_ledger.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/modelo/test_iva_wallet_decision_binding.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py -q` completed with 59 passed.
- `uv run ruff check src/aeat/application/aggregation/_iva_ledger.py src/aeat/application/aggregation/__init__.py src/aeat/application/aggregation/test_iva_ledger.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/modelo/test_iva_wallet_decision_binding.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py` passed.
- `git diff --check -- src/aeat/application/aggregation/_iva_ledger.py src/aeat/application/aggregation/__init__.py src/aeat/application/aggregation/test_iva_ledger.py src/aeat/application/modelo/test_bucket_aggregation_flow.py` passed.

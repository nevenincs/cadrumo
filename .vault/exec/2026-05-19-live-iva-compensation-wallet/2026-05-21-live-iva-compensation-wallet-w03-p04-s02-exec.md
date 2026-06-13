---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# W03.P04.S02 IVA wallet authority-source separation

## Scope

- Step: `W03.P04.S02`
- Goal: keep AEAT wallet evidence, local recurrence, filed-history observations, and explicit taxpayer overrides as separate authority sources.

## Changes

- Added `IvaCompensationAuthoritySource` records to persisted IVA wallet reconciliation decisions.
- Reconciliation now records AEAT wallet captures, local recurrence values, filed-history observations, and taxpayer overrides as separate source records.
- The application reconciliation path maps a local Modelo 303 recurrence to both the derived `local_recurrence` source and the underlying `filed_history_observation` source with modelo/year/period provenance.
- Tests now assert the authority-source set for direct reconciliation and for a real Modelo 303 prior-filing history flow.

## Verification

- `uv run pytest src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/calculations/test_observations_repository_roundtrip.py -q`
- `uv run ruff check src/aeat/application/calculations/_iva_wallet_reconciliation.py src/aeat/application/calculations/__init__.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py`
- `git diff --check -- src/aeat/application/calculations/_iva_wallet_reconciliation.py src/aeat/application/calculations/__init__.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/modelo/_actions.py src/aeat/application/modelo/test_bucket_aggregation_flow.py .vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md .vault/audit/2026-05-20-live-iva-compensation-wallet-review.md .vault/exec/2026-05-19-live-iva-compensation-wallet/2026-05-21-live-iva-compensation-wallet-w03-p04-s01.md`

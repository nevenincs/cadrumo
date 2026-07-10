---
tags:
  - '#exec'
  - '#cpdefix-followup-allgreen'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S20'
related:
  - "[[2026-07-05-cpdefix-followup-allgreen-plan]]"
---
# Replace renta income aggregation test-export repository imports with real persistence adapter sources

## Scope

- `src/aeat/application/aggregation/tests/test_renta_income_source_jurisdiction_m100.py`
- `src/aeat/application/aggregation/tests/test_impatriado_income_ledger.py`

## Description

- Grounded the cleanup with `uvx vaultspec-rag search "remaining application_adapter_exports TransactionCatalogueRepository tests real adapter source aggregation ledger" --type code`.
- Confirmed `TransactionCatalogueRepository` is defined in `src/aeat/adapters/persistence/profile/transactions.py` and `SecureObjectRepository` is defined on the storage SQL adapter surface used by the existing real-storage tests.
- Replaced the `src/aeat/tests/application_adapter_exports.py` imports in the renta resident and impatriado income aggregation tests with direct imports from the concrete adapter modules.

## Outcome

The renta income source-jurisdiction and Modelo 151 impatriado aggregation tests now provision repository/storage dependencies from their real adapter sources. The legal-calculation assertions for LIRPF art. 8 universal-base handling and art. 93 / TRLIRNR Spanish-source scope remain covered by the same real-behavior tests.

Focused gates passed:

- `uv run --no-sync ruff check src/aeat/application/aggregation/tests/test_renta_income_source_jurisdiction_m100.py src/aeat/application/aggregation/tests/test_impatriado_income_ledger.py` - passed.
- `uv run --no-sync pytest -q src/aeat/application/aggregation/tests/test_renta_income_source_jurisdiction_m100.py src/aeat/application/aggregation/tests/test_impatriado_income_ledger.py -n 0` - `17 passed`.

## Notes

No production code changed. This step only removes test-export provisioning from two legal-scope aggregation test surfaces.

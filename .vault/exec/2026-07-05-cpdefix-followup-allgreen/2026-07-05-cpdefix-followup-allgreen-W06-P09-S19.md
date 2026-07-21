---
tags:
  - '#exec'
  - '#cpdefix-followup-allgreen'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S19'
related:
  - "[[2026-07-05-cpdefix-followup-allgreen-plan]]"
---
# Replace memoized transaction test-export repository import with the real persistence adapter source

## Scope

- `src/aeat/application/modelo/tests/test_memoized_transaction_catalogue_repository.py`

## Description

- Grounded the cleanup with `uvx vaultspec-rag search "application_adapter_exports remaining direct source repository test imports transaction catalogue attachment store llm telemetry" --type code`.
- Confirmed `TransactionCatalogueRepository` is defined in `src/aeat/adapters/persistence/profile/transactions.py` and is the concrete encrypted SQL-backed repository named by this test's docstring.
- Replaced the import from `src/aeat/tests/application_adapter_exports.py` with a direct import from the real transaction persistence adapter.

## Outcome

The memoized transaction-catalogue wrapper test now provisions the real concrete repository from its defining adapter module, while continuing to exercise encrypted secure-object storage through `isolated_runtime_profile`.

Focused gates passed:

- `uv run --no-sync ruff check src/aeat/application/modelo/tests/test_memoized_transaction_catalogue_repository.py` - passed.
- `uv run --no-sync pytest -q src/aeat/application/modelo/tests/test_memoized_transaction_catalogue_repository.py -n 0` - `5 passed`.

## Notes

No production code changed. This is a direct-source test cleanup for the no-reexport campaign constraint.

---
tags:
  - '#exec'
  - '#cpdefix-followup-allgreen'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:479f982285c3891362dbadc53a62249e340eff4813c654bfcb118d8fddebee32'
step_id: 'S25'
related:
  - "[[2026-07-05-cpdefix-followup-allgreen-plan]]"
---
# Execution Notes

## Grounding
- RAG search: `uvx vaultspec-rag search "application_adapter_exports calculation revision work unit modelo record attachment store secure object repository modelo tests real source" --type code --max-results 12`.
- Concrete sources confirmed from `src/aeat/tests/application_adapter_exports.py` and adapter modules:
  - `BucketEventHistoryRepository` -> `src/aeat/adapters/persistence/profile/buckets`
  - `CalculationRevisionCatalogueRepository` -> `src/aeat/adapters/persistence/profile/modelos_calculation`
  - `ModeloRecordCatalogueRepository` -> `src/aeat/adapters/persistence/profile/modelos_filing`
  - `WorkUnitCatalogueRepository` -> `src/aeat/adapters/persistence/profile/modelos_work_units`

## Change
Replaced `src/aeat/application/modelo/tests/test_amend_kind_resolution.py` imports from `src/aeat/tests/application_adapter_exports.py` with direct concrete repository imports.

## Verification
- `uv run --no-sync ruff check src/aeat/application/modelo/tests/test_amend_kind_resolution.py` -> passed.
- `uv run --no-sync pytest -q src/aeat/application/modelo/tests/test_amend_kind_resolution.py -n 0` -> `6 passed`.

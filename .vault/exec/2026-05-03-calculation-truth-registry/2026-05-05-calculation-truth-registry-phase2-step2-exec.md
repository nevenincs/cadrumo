---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-05-calculation-truth-registry-phase2-step2-review-audit]]'
---



# `calculation-truth-registry` `Phase 2` `Step 2`

Replaced direct filing draft test construction with registry-backed draft helper
behaviour.

- Deleted: `src/aeat/application/filing/_testing_synthesize.py`
- Deleted: `src/aeat/application/filing/test_testing_synthesize.py`
- Created: `src/aeat/application/filing/_testing_registry.py`
- Created: `src/aeat/application/filing/test_testing_registry.py`
- Modified: `src/aeat/application/filing/testing.py`
- Modified: `src/aeat/application/filing/test_filing.py`
- Modified: `src/aeat/application/filing/test_complementaria.py`
- Modified: `src/aeat/application/filing/_test_repository.py`
- Modified: `src/aeat/application/filing/_test_complementaria_repository.py`
- Modified: `src/aeat/application/filing/test_import.py`
- Modified: `src/aeat/application/filing/test_schema_completeness.py`
- Modified: `src/aeat/application/filing/reconciliation/test_reconcile.py`
- Modified: `src/aeat/application/filing/runtime.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`
- Created: `.vault/audit/2026-05-05-calculation-truth-registry-phase2-step2-review.md`

## Description

The public filing test helper now builds drafts through `build_draft`,
`build_runtime_schema_provider`, and `approve_draft`. It fails at the registry
boundary for unsupported modelos and incomplete Modelo 130 binding inputs.

Filing repository and complementaria tests now supply the Modelo 130
previous-filing binding explicitly. Import tests now assert the real current
behaviour: a justificante-only Modelo 130 import cannot calculate without the
required binding data.

## Tests

`uv run pytest src\aeat\application\filing\test_testing_registry.py src\aeat\application\filing\test_filing.py src\aeat\application\filing\_test_repository.py src\aeat\application\filing\_test_complementaria_repository.py src\aeat\application\filing\test_complementaria.py src\aeat\application\filing\test_import.py src\aeat\application\filing\test_schema_completeness.py src\aeat\application\filing\reconciliation\test_reconcile.py -q`

`uv run ruff check src\aeat\application\filing\_testing_registry.py src\aeat\application\filing\testing.py src\aeat\application\filing\test_testing_registry.py src\aeat\application\filing\test_filing.py src\aeat\application\filing\_test_repository.py src\aeat\application\filing\_test_complementaria_repository.py src\aeat\application\filing\test_complementaria.py src\aeat\application\filing\reconciliation\test_reconcile.py src\aeat\application\filing\test_import.py src\aeat\application\filing\test_schema_completeness.py src\aeat\application\filing\runtime.py`

`uv run ty check src\aeat\application\filing\_testing_registry.py src\aeat\application\filing\testing.py src\aeat\application\filing\test_testing_registry.py src\aeat\application\filing\test_filing.py src\aeat\application\filing\_test_repository.py src\aeat\application\filing\_test_complementaria_repository.py src\aeat\application\filing\test_complementaria.py src\aeat\application\filing\reconciliation\test_reconcile.py src\aeat\application\filing\test_import.py src\aeat\application\filing\test_schema_completeness.py src\aeat\application\filing\runtime.py`

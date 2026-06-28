---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-05-calculation-truth-registry-phase2-step3-review-audit]]'
---



# `calculation-truth-registry` `Phase 2` `Step 3`

Removed the filing-history fixture schema and its separate fixture corpus.

- Deleted: `src/aeat/application/filing/_testing_schema.py`
- Deleted: `src/aeat/application/filing/_testing_loader.py`
- Deleted: `tests/import_contract/application/filing/test_testing.py`
- Deleted: `tests/fixtures/filing_history`
- Modified: `src/aeat/application/filing/testing.py`
- Modified: `src/aeat/application/filing/test_filing.py`
- Modified: `src/aeat/application/filing/test_complementaria.py`
- Modified: `src/aeat/application/filing/test_modelo_303_390.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`
- Created: `.vault/audit/2026-05-05-calculation-truth-registry-phase2-step3-review.md`

## Description

The filing test utility no longer exports a separate filing-history schema,
record loader, record-id helper, or fixture corpus. Tests now use registry-backed
draft helpers and public filing APIs.

The test profile/deadline helpers were renamed to `FilingTestProfile`,
`FilingTestDeadlineStatus`, and `FilingTestDeadlineChecker` with no compatibility
aliases.

## Tests

`uv run pytest src\aeat\application\filing\test_testing_registry.py src\aeat\application\filing\test_filing.py src\aeat\application\filing\test_complementaria.py src\aeat\application\filing\test_modelo_303_390.py -q`

`uv run ruff check src\aeat\application\filing\testing.py src\aeat\application\filing\test_filing.py src\aeat\application\filing\test_complementaria.py src\aeat\application\filing\test_modelo_303_390.py`

`uv run ty check src\aeat\application\filing\testing.py src\aeat\application\filing\test_filing.py src\aeat\application\filing\test_complementaria.py src\aeat\application\filing\test_modelo_303_390.py`

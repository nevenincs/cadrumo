---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-03'
modified: '2026-05-03'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-phase5-step5-exec]]'
---



# `calculation-truth-registry` Code Review

CALC-REG-006 | INFO | No blocking findings for public filing builder export removal

Review confirmed that `aeat.domain.filing` no longer imports or exports
`get_builder`, concrete builder classes, or `QUARTERLY_303_INPUT_KEY`, and that
application draft construction remains fail-closed behind the validated
registry snapshot boundary.

CALC-REG-007 | INFO | Private legacy builder package remains importable

Review identified `aeat.domain.filing._builders` as a remaining direct
importability residual. This is not a blocker for the public facade slice, but
it is the next Phase 5 teardown target.

Post-fix verification:

- `uv run --no-sync ruff check src\aeat\domain\filing\__init__.py src\aeat\application\filing\__init__.py src\aeat\application\filing\_complementaria.py src\aeat\application\filing\test_complementaria.py tests\import_contract\test_registry_deletion_gates.py`
- `uv run --no-sync ty check src\aeat\domain\filing src\aeat\application\filing tests\import_contract\test_registry_deletion_gates.py`
- `uv run --no-sync pytest tests\import_contract\test_registry_deletion_gates.py src\aeat\application\filing\test_complementaria.py src\aeat\application\filing\test_filing.py src\aeat\application\filing\test_modelo_303_390.py src\aeat\application\filing\test_import.py src\aeat\entrypoints\cli\filing\test_filing_cli.py`
- `uv run --no-sync pytest src\aeat\application\filing tests\import_contract\test_registry_deletion_gates.py src\aeat\entrypoints\cli\filing\test_filing_cli.py`

Result: static checks passed; focused filing tests passed 66 tests; filing
slice passed 206 tests with 4 pre-existing skipped reconciliation tests.

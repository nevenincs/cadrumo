---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-03'
modified: '2026-05-03'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-phase5-step4-exec]]'
---



# `calculation-truth-registry` Code Review

CALC-REG-004 | HIGH | Complementaria tests still depended on legacy draft construction

Resolved. `test_complementaria.py` now persists original drafts using the
application synthetic draft helper and asserts complementaria construction fails
closed until a validated registry snapshot exists. The repository tests now use
the same synthetic draft path, so persistence coverage remains without
dispatching old model-specific builders.

CALC-REG-005 | LOW | Public `build_draft` docstring described legacy success semantics

Resolved. The docstring now states that public draft construction is rejected
until a validated registry snapshot builder replaces the disabled legacy Python
filing builders.

Post-fix verification:

- `uv run --no-sync ruff check src\aeat\application\filing\__init__.py src\aeat\application\filing\test_filing.py src\aeat\application\filing\test_modelo_303_390.py src\aeat\application\filing\test_import.py src\aeat\application\filing\test_complementaria.py src\aeat\application\filing\_test_repository.py src\aeat\application\filing\_test_complementaria_repository.py tests\import_contract\test_registry_deletion_gates.py`
- `uv run --no-sync ty check src\aeat\application\filing tests\import_contract\test_registry_deletion_gates.py`
- `uv run --no-sync pytest src\aeat\application\filing tests\import_contract\test_registry_deletion_gates.py src\aeat\entrypoints\cli\filing\test_filing_cli.py`

Result: static checks passed; filing slice passed 205 tests with 4 pre-existing
skipped reconciliation tests.

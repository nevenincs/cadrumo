---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-03'
modified: '2026-05-03'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `calculation-truth-registry` `phase5` `step6`

Deleted the legacy domain filing builder package and removed model-specific
303/390 calculation truth from the filing validator.

- Deleted: `src/aeat/domain/filing/_builder.py`
- Deleted: `src/aeat/domain/filing/_builders/__init__.py`
- Deleted: `src/aeat/domain/filing/_builders/_modelo_130_schema.py`
- Deleted: `src/aeat/domain/filing/_builders/_modelo_303_schema.py`
- Deleted: `src/aeat/domain/filing/_builders/_modelo_390_schema.py`
- Deleted: `src/aeat/domain/filing/_builders/modelo_130.py`
- Deleted: `src/aeat/domain/filing/_builders/modelo_303.py`
- Deleted: `src/aeat/domain/filing/_builders/modelo_390.py`
- Modified: `src/aeat/domain/filing/__init__.py`
- Modified: `src/aeat/application/filing/__init__.py`
- Modified: `src/aeat/domain/filing/_validator.py`
- Modified: `src/aeat/application/filing/test_modelo_303_390.py`
- Modified: `tests/import_contract/test_registry_deletion_gates.py`

## Description

The old `FilingBuilder` ABC and concrete Modelo 130, 303, and 390 builder
package were deleted. Public domain and application filing packages no longer
import or export `FilingBuilder`.

The filing validator was reduced to cross-cutting validation only: schema
version, required casillas, range checks, formula-trace shape checks, and
deadline checks. The hardcoded Modelo 390 to Modelo 303 casilla map, Modelo
303 VAT-rate triples, reconciliation tolerance, and quarterly reconciliation
runtime were removed because they were model-specific calculation authority
outside registry snapshots.

Import-contract tests now prove the deleted builder files and directory are
absent, the public packages cannot export builder surfaces, and the filing
validator does not own the removed model-specific calculation truth.

## Tests

Verified with targeted `ruff check`, `ty check`, and the application filing
slice:

- `uv run --no-sync ruff check src\aeat\domain\filing src\aeat\application\filing tests\import_contract\test_registry_deletion_gates.py`
- `uv run --no-sync ty check src\aeat\domain\filing src\aeat\application\filing tests\import_contract\test_registry_deletion_gates.py`
- `uv run --no-sync pytest tests\import_contract\test_registry_deletion_gates.py src\aeat\application\filing src\aeat\entrypoints\cli\filing\test_filing_cli.py`

Result: static checks passed; filing slice passed 206 tests with 4 pre-existing
skipped reconciliation tests.

Review evidence is recorded in
`2026-05-03-calculation-truth-registry-phase5-step6-review`.

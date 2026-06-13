---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `calculation-truth-registry` `phase2` `step12`

Removed hardcoded annual-modelo period authority from justificante parsing and
kept receipt parsing as observed artefact extraction.

- Modified: `src/aeat/adapters/inbound/justificante/_extract.py`
- Modified: `src/aeat/adapters/inbound/justificante/test_extract_modelos.py`
- Modified: `src/aeat/application/filing/_import.py`
- Modified: `src/aeat/application/filing/test_import.py`
- Modified: `src/aeat/application/filing/runtime.py`
- Modified: `src/aeat/application/filing/reconciliation/_reconcile.py`
- Modified: `src/aeat/application/filing/reconciliation/test_reconcile.py`
- Modified: `tests/import_contract/adapters/inbound/justificante/test_parser.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

`_extract.py` no longer carries a Python set of annual modelos. When a
justificante has no explicit period token but does print an ejercicio, the
parser preserves that observed year as the receipt period instead of deriving
`0A` from modelo identity.

Runtime schema subviews now expose the active registry revision's declared
period selector. Application import and reconciliation only canonicalise
year-only receipt periods to annual draft periods when that active registry
revision declares `0A`; quarterly registry revisions reject the year-only
annual interpretation instead of accepting it generically.

The justificante import-contract corpus now asserts observed PDF period output
instead of treating the fixture filename as hidden period authority. Fixtures
that print `0A` remain `0A`; fixtures that print only the ejercicio preserve
the ejercicio as the observed receipt period.

## Tests

- `uv run pytest src\aeat\adapters\inbound\justificante src\aeat\application\filing\test_import.py src\aeat\application\filing\reconciliation -q`
  passed: 47 tests.
- `uv run pytest src\aeat\adapters\inbound\borrador src\aeat\adapters\inbound\justificante src\aeat\application\filing\test_import.py src\aeat\application\filing\reconciliation tests\import_contract\adapters\inbound\justificante\test_parser.py -q`
  passed: 104 tests.
- `uv run ruff check src\aeat\adapters\inbound\justificante src\aeat\application\filing\_import.py src\aeat\application\filing\test_import.py src\aeat\application\filing\reconciliation`
  passed.
- `uv run ty check src\aeat\adapters\inbound\justificante src\aeat\application\filing\_import.py src\aeat\application\filing\test_import.py src\aeat\application\filing\reconciliation`
  passed.

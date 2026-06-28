---
tags:
  - '#exec'
  - '#justfile-redesign'
date: '2026-06-09'
modified: '2026-06-09'
step_id: 'S04'
related:
  - "[[2026-06-09-justfile-redesign-plan]]"
---

# relocate test_workbook_parity.py to nested workbook_parity directory

## Scope

- `src/aeat/domain/calculations/registry/tests/workbook_parity/test_workbook_parity.py`
- `src/aeat/domain/calculations/registry/tests/workbook_parity/__init__.py`

## Description

- Created a new nested directory `src/aeat/domain/calculations/registry/tests/workbook_parity`.
- Relocated `test_workbook_parity.py` into the new directory.
- Created an empty `__init__.py` package marker.
- Updated all relative imports inside `test_workbook_parity.py` to match the new nesting level (`......core.errors`, `......core.resources`, `..._loader`, `..._schema`, `..._snapshot`, `..._workbook_parity`).

## Outcome

Verification via `pytest --collect-only` confirms that the 18 tests contained in `test_workbook_parity.py` are collected successfully without errors under the new directory path.

## Notes

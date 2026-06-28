---
tags:
  - "#exec"
  - "#pytest-markers"
date: 2026-04-17
modified: '2026-04-17'
related:
  - "[[2026-04-17-pytest-markers-plan]]"
  - "[[2026-04-17-pytest-markers-adr]]"
---

# pytest-markers phase-2 step-3

## add-marker-integrity-ast-walker

Created `tests/test_marker_integrity.py` carrying its own module-level `pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]`. The module:

- Globs every `test_*.py` / `_test_*.py` under `src/aeat/**` and `tests/**`, excluding `__init__.py` and `tests/fixtures/**` helpers.
- For each discovered file, parses with `ast`, locates the unique top-level `pytestmark = [...]` assignment, and records each element's marker name.
- Accepts both attribute-chain elements (`pytest.mark.<name>`) and call elements (`pytest.mark.skipif(...)`) so the google-fixtures module's skipif guard is preserved.
- Parametrizes one test per module so each failure line names its own file.
- Self-validates (the glob includes `tests/test_marker_integrity.py`).

Files touched:
- `tests/test_marker_integrity.py` (new)

## verification

- `uv run pytest tests/test_marker_integrity.py` -> 148 passed.

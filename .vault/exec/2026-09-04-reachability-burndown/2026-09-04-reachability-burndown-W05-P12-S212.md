---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:f74744f24829e5f3f9f7f0e12498f77ba2940e0491a25ca4ab6785308a138a38'
step_id: 'S212'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Move the detail-row identity-table coverage comparison entirely out of production calculation adjustments by deleting the test-only uncovered_detail_row_kinds facade and private comparison helper, and make the focused gate derive ModeloDetailRow union members against the live identity table inside the test while retaining detector-teeth proof and all runtime union/conflict behavior.

## Scope

- `Modelo calculation adjustments and focused identity-union tests`
- `exact reachability signal`
- `focused gates`
- `cadence reference`
- `Step Record`
- `and independent code review.`

## Changes

- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `src/cadrumo/application/modelo/_calculation_modelo_adjustments.py`
- `M` `src/cadrumo/application/modelo/tests/test_calculation_modelo_adjustments.py`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/modelo/_calculation_modelo_adjustments.py src/cadrumo/application/modelo/tests/test_calculation_modelo_adjustments.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 -m "" --basetemp <isolated-workspace-temp> src/cadrumo/application/modelo/tests/test_calculation_modelo_adjustments.py` -> `pass` (7 passed)
- `verify:` `rg -n "uncovered_detail_row_kinds|_uncovered_row_kinds" src/cadrumo --glob '*.py'` -> `pass` (no matches)
- `verify:` `uv run --no-sync python -m dev.quality.production_metastate` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `findings` (314 exact unused symbols; target absent)

## Notes

The exact unused-symbol count fell from 315 immediately before S212 to 314 after removal of the public coverage facade; the private helper removed with it was previously reachable only through that facade. The live graph remained at 63 unreachable modules, 15 orphaned tests, and 2028/2092 shipped modules reachable.

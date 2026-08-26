---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:30d86d6a5f76117f5997db6d0a17885edbfd4ef86bfc9e5ada180d9f7db75598'
step_id: 'S25'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Prove C1 review outliers, stable keyboard order, non-colour status, and all four locales, three geometries, and two themes before its route can become callable

## Scope

- `src/cadrumo/entrypoints/tui/modelo/tests/test_c1_bounded_review.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/modelo/tests/__init__.py`
- `A` `src/cadrumo/entrypoints/tui/modelo/tests/test_c1_bounded_review.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/modelo/tests/test_c1_bounded_review.py -q` -> `pass` (10 passed)
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/modelo/view/tests/test_work_review.py -q` -> `pass` (13 passed, unaffected)

## Notes

These 10 tests target the NEW select-screen destination specifically
(keyboard-only row selection returning the exact chosen `work_unit_id`,
quit-without-choosing, empty catalogue, non-colour state distinguishability,
four locales, three geometries, two themes, and a foreign-App-host refusal).
The review screen's own internal accessibility matrix (facets, locale,
geometry, theme, keyboard scroll) was already proven exhaustively by the
pre-existing `view/tests/test_work_review.py` and is not duplicated here.
Writing the first real keyboard-selection test caught a genuine production
bug: `DataTable` owns the `enter` key itself (bound to `select_cursor`) and
never lets it bubble to a screen-level `Binding("enter", ...)`, so the
original `action_confirm_select` binding never fired. Fixed by handling
`DataTable.RowSelected` directly in `work_select.py` (see W05.P10.S24).

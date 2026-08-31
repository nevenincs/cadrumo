---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:dffaa42d73d04f06c060f5509a70b69481e844c1694202ec8abc15423b474c51'
step_id: 'S22'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Extend the settled guided-flow shell with reusable stage navigation validation summaries and cancellation

## Scope

- `src/cadrumo/entrypoints/tui/flows/app.py`

## Changes

- `M` `src/cadrumo/entrypoints/tui/flows/app.py`
- `M` `src/cadrumo/entrypoints/tui/components/widgets.py`
- `M` `src/cadrumo/locales/{ca,en,es,hu}/flows.yml`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/tests/test_flow_tui_app.py src/cadrumo/entrypoints/tui/flows/ -q -m "unit or integration"` -> `pass` (46 passed, 2 pre-existing unrelated failures)

## Notes

Cancellation and validation summaries were already settled: the existing save-and-exit action (ctrl+s) and the existing #review-blocking aggregate verdict block. Only the section-level stage strip was a real gap; StageNavigationStrip gained set_current_index rather than a forked variant.

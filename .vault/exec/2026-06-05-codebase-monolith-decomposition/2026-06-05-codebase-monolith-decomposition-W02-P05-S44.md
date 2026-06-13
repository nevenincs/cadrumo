---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S44'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S44 - select google config closure command group

Scope: `src/aeat/entrypoints/cli/_config/_google.py src/aeat/entrypoints/cli/_config/tests`.

## Description

- Inspect the residual `_google.py` command topology after the folder extraction.
- Use exact discovery to locate the remaining Google command groups, command tests, and direct test imports.
- Use semantic discovery for `google sync calc` command functions inside `_google.py`.
- Select the `sync calc` subgroup for extraction into a focused Google config module.

## Outcome

Selected the `aeat config google sync calc` subgroup. Exact discovery showed the subgroup owns `google_sync_calc_export`, `google_sync_calc_verify`, `google_sync_calc_pull`, `calc_app`, and pull assembly helpers from the lower half of `_google.py`; semantic search returned the calc command functions as the top matching code nodes for the Google sync calc query. The direct test surface is `test_google_sync_calc_pull_flag.py`, which currently imports `google_sync_calc_pull` from `_google.py`.

## Notes

The extraction should preserve the public `_google.py` import surface for `_google_refusal` and `google_sync_calc_pull`, or update the focused tests to import from the new calc module. A shared Google refusal helper is the cleanest way to avoid a calc module importing back from `_google.py`.

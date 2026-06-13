---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S45'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S45 - extract google config closure command group

Scope: `src/aeat/entrypoints/cli/_config/_google.py src/aeat/entrypoints/cli/_config/*.py`.

## Description

- Preserve the already staged Google Drive `folder` extraction in `_google_folder.py`.
- Add `_google_errors.py` for the shared Google refusal wrapper used by the facade and focused Google modules.
- Add `_google_sync_calc.py` as the focused registrar module for `config google sync calc`.
- Move calc export, verify, pull, snapshot loading, credential/root resolution, and pull helper functions out of `_google.py`.
- Mount the extracted calc subgroup through `register_google_sync_calc_commands`.

## Outcome

The Google folder and sync calc command surfaces are extracted without changing operator command paths. `_config/_google.py` now delegates folder and sync calc mounting to focused modules and dropped to 734 lines.

## Notes

Ruff and focused Google CLI tests passed for the extracted modules and facade.

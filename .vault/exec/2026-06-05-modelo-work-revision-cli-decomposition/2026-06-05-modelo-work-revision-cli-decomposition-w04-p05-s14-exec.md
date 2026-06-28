---
tags: ['#exec', '#modelo-work-revision-cli-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S14'
related:
  - '[[2026-06-05-modelo-work-revision-cli-decomposition-plan]]'
---

# W04.P05.S14 Execution

Extracted the live `borrador 100` subgroup into `src/aeat/entrypoints/cli/_app_live_borrador_cli.py`.

Implementation:
- Added `borrador_app`, `borrador_100_app`, and `register_borrador_commands`.
- Replaced the root command bodies in `_app_live.py` with a registrar mount.
- Preserved the existing test import surface by re-exporting `borrador_app` and `borrador_100_app` from `_app_live.py`.

Outcome:
- `_app_live.py` line count moved from 2262 to 2061.

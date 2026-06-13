---
tags: ['#exec', '#modelo-work-revision-cli-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S07'
related:
  - '[[2026-06-05-modelo-work-revision-cli-decomposition-plan]]'
---

# W02.P03.S07 Execution

Replaced the legacy `work verify` and `work file` command bodies in `src/aeat/entrypoints/cli/_modelo.py` with registrar mounting.

Outcome:
- `_modelo.py` now mounts `register_work_verification_commands`.
- Direct verify/file action imports were removed from `_modelo.py`.
- `_modelo.py` line count dropped from 2070 after W01 to 1881 after W02.

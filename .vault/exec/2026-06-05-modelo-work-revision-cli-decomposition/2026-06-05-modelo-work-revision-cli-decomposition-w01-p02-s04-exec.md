---
tags: ['#exec', '#modelo-work-revision-cli-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S04'
related:
  - '[[2026-06-05-modelo-work-revision-cli-decomposition-plan]]'
---

# W01.P02.S04 Execution

Replaced the legacy revision read command bodies in `src/aeat/entrypoints/cli/_modelo.py` with registrar mounting.

Outcome:
- `_modelo.py` now imports and mounts `register_work_revision_commands`.
- The legacy command bodies and direct rendering-helper imports were removed from `_modelo.py`.
- `_modelo.py` line count dropped from the previous 2242-line frozen budget to 2070 lines.

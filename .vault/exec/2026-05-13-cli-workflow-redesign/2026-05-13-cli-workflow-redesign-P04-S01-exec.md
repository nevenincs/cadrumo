---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P04.S01'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P04.S01`

Wired the `secure_state.load` fail branch in
`src/aeat/application/diagnostics.py` to carry
`next_action="aeat config repair reset-state --yes"` and dropped the
P02 placeholder `dead_end` string that mentioned the
config-repair-shape phase. The discriminated-union contract permits
exactly one of `next_action` / `dead_end`; this row now points the
operator at the new recovery route landed in P03.

- Modified: `src/aeat/application/diagnostics.py`

## Tests

`pytest src/aeat/application/test_diagnostics.py
src/aeat/application/test_diagnostics_dispatch.py
src/aeat/application/workflow/` — 74 passed.

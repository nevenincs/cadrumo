---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P04.S07'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P04.S07`

Stripped the textual recovery hint and the `suggestion=` kwarg from
the `WorkflowError` raised when
`WorkflowStateRepository.load` cannot validate the persisted envelope.
The message now reads `Local configuration state could not be read.`
The diagnostic row's `next_action` is the single source of operator
recovery guidance; the exception no longer duplicates it (and no
longer references the renamed-away `doctor` command).

- Modified: `src/aeat/application/workflow/_persistence.py`

## Tests

`pytest src/aeat/application/workflow/` 33 passed.

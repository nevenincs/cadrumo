---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P03.S03'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P03.S03`

Wired the `workflow_state.reset` emission into the same logical
transaction as the secure-object delete.

- Modified: `src/aeat/application/workflow/_persistence.py`

## Description

`WorkflowStateRepository.reset_workflow_state` captures the
fingerprint before mutating, performs
`SecureObjectRepository.delete(_STATE_NAMESPACE, _STATE_OBJECT_KEY)`,
and then calls `emit_workflow_state_reset(...)` from the application
events module. The three calls execute in sequence inside the same
method body, matching the existing emission pattern in
`application/profile/_actions.py` (capture state, mutate, emit). The
mutation and the event are part of the same boundary call, so the
operator-visible audit trail is consistent with the storage state.

A debug log line records the reset; no plaintext envelope content is
written to logs.

## Tests

Covered by the same CLI test as P03.S02; the catalogue is read post-
mutation to confirm the event was appended.

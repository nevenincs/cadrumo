---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P03.S02'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P03.S02`

Added `workflow_state.reset` to the bucket-event taxonomy with a
typed pydantic payload carrying the envelope fingerprint plus actor
metadata.

- Modified: `src/aeat/domain/buckets/_event.py`
- Created: `src/aeat/application/workflow/_events.py`

## Description

`BucketEventType.WORKFLOW_STATE_RESET = "workflow_state.reset"` was
added to the closed enum. A companion `BucketEventObjectType.WORKFLOW_STATE
= "workflow_state"` was added because the event targets a singleton
configuration row, not any of the existing modelo or profile object
types.

The application-layer module `_events.py` owns the typed payload
contract:

- `WorkflowStateResetFingerprint` — strict frozen pydantic model with
  fields `schema_version: int | None`, `written_at: datetime | None`,
  `byte_length: int | None`, `reason_class: str`, and
  `recovered_bucket_id: str | None`. All optionality matches the
  ADR's "row may be present or absent, envelope may be readable or
  not" semantics.
- `WorkflowStateResetEvent` — strict frozen pydantic model bundling
  the fingerprint with `actor`, `source`, and `timestamp`.
- `emit_workflow_state_reset(*, fingerprint, actor, source)` — emits
  one `workflow_state.reset` bucket event through the existing
  `BucketEventHistoryRepository.load` → `append_bucket_event` →
  `BucketEventHistoryRepository.save` pattern, mirroring the
  profile-event emitter in `application/profile/_actions.py`.

The event bucket id is the recovered active profile bucket when one
survives on the fingerprint, or the constant `SYSTEM_BUCKET_ID =
"system"` otherwise (per the ADR's "active bucket if recoverable, or
system bucket" rule). The event object id is the constant
`WORKFLOW_STATE_OBJECT_ID = "aeat.workflow:state"`, naming the single
storage row the recovery flow targets. The payload mapping projects
the typed event onto the short-string bucket-event payload contract;
no plaintext envelope content is recorded.

## Tests

Covered indirectly by `test_repair_reset_state.py`'s
`test_reset_state_with_yes_deletes_row_emits_event_and_reload_is_empty`,
which asserts exactly one `BucketEventType.WORKFLOW_STATE_RESET` event
is appended to the catalogue after the mutation.

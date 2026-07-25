---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S66'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Persist deleting ownership before deletion and completion after each irreversible transition

## Scope

- `src/cadrumo/application/config_reset.py`

## Description

- Construct the deletion marker carrying the operation id, bucket id, and recorded fingerprint, advance the target to the deleting phase, and save the journal before the delete call is issued.
- Skip re-marking a target already at the deleting phase, so a resumed operation reuses the marker it previously persisted rather than minting a second one.
- Issue the delete through the bucket-maintenance service carrying the operation id and expected fingerprint, so the service can verify ownership against the very marker just persisted.
- Advance the target to the deleted phase with the completion timestamp taken from the deletion result and save the journal immediately after the delete returns.
- Advance an absent target directly to the deleted phase with a completion timestamp, saving after each such transition.
- Build the reconciled summary and persist the complete status only after every target has reached the deleted phase, clearing any pause reason and paused target ids in the same write.

## Outcome

- Ownership is durable before the irreversible act it authorizes: the marker reaches disk before deletion begins, so a crash between marking and erasing leaves a journal that proves which operation owned the target.
- Completion is durable after the irreversible act: the deleted phase and its timestamp are saved immediately, so a crash after erasing cannot cause the target to be attempted a second time as though untouched.
- The model layer independently enforces this ordering, requiring a marker for a deleting target and exactly one completion timestamp for a deleted target, so an inverted write cannot validate.
- The operation is marked complete only once every target is deleted and the summary counts reconcile against the target set.
- Landed in commit `60135859e2`.

## Notes

- The work was already committed when this record was curated; the record documents the landed state verified against `HEAD` rather than a fresh edit.
- The marker is reused rather than regenerated on resume, so the fingerprint the service verifies is the one recorded before the first deletion attempt.

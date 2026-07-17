---
tags:
  - '#exec'
  - '#export-publication'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S11'
related:
  - "[[2026-07-17-export-publication-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace export-publication with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S11 and 2026-07-17-export-publication-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Decide and implement whether a crash after os.replace succeeds but before the PROFILE_EXPORTED audit event eventually emits that event: adopt the three-phase journal (PREPARED, then replace plus fsync transitioning to COMPLETED, then emit the event, with reconcile completing a COMPLETED-but-eventless operation), closing the un-audited data-egress window and wiring the currently-dead COMPLETED operation-state enum, a data-egress audit-completeness posture item with limited privacy impact (a local file at the operator own path, not remote transmission), gated on no durably-published bundle lacking a PROFILE_EXPORTED event after reconcile and ## Scope

- `src/cadrumo/application/user_profile/_bundle_export.py`
- `src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Decide and implement whether a crash after os.replace succeeds but before the PROFILE_EXPORTED audit event eventually emits that event: adopt the three-phase journal (PREPARED, then replace plus fsync transitioning to COMPLETED, then emit the event, with reconcile completing a COMPLETED-but-eventless operation), closing the un-audited data-egress window and wiring the currently-dead COMPLETED operation-state enum, a data-egress audit-completeness posture item with limited privacy impact (a local file at the operator own path, not remote transmission), gated on no durably-published bundle lacking a PROFILE_EXPORTED event after reconcile

## Scope

- `src/cadrumo/application/user_profile/_bundle_export.py`
- `src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py`

## Description

- Extend the operation record with the staged payload's SHA-256 digest and a fixed `event_occurred_at`, and wire the previously-dead `COMPLETED` operation-state.
- Rewrite publication as a three-phase durable sequence: atomic replace + parent fsync (the durability point), transition the journal to `COMPLETED`, then emit the `PROFILE_EXPORTED` event from the fixed `event_occurred_at`, then clear the journal.
- Rewrite the event-failure contract: a completion event that fails after a successful replace leaves the bundle published and the `COMPLETED` journal in place for reconcile to finish, never restoring the preexisting target (which could un-publish durable data).
- Rewrite reconciliation to complete every published operation — a `COMPLETED` one, or a `PREPARED` one whose destination content matches the recorded digest (the replace landed but the `COMPLETED` transition did not) — by emitting the owed event idempotently, and to clear a digest-mismatched `PREPARED` operation as an orphan with no event.
- Emit the event solely from the durable operation record so a live emission and a reconciliation emission collapse to one content-addressed event.

## Outcome

Closes the un-audited-egress window the durable-layer review surfaced: no durably-published bundle is left without its `PROFILE_EXPORTED` event after reconcile, and no durably-written bundle is ever un-published. Four real-behavior proofs pass (crash between replace and completion → one event via digest; digest-mismatch orphan → no event; idempotent reconcile; event-write failure → published + reconcile emits the pending event), plus the full `user_profile` suite (176 passed) and the error-registry gate. Committed in `7b81a87b36`.

## Notes

Idempotency rests on the content-addressed event catalogue (`append_bucket_event` collapses a re-emission with the same `event_id`) plus the stored `event_occurred_at`, so re-running reconcile — or a live emission followed by a reconcile emission — yields exactly one event. This is a deliberate contract change from the prior restore-on-event-failure behaviour; the superseded `test_event_failure...restores_preexisting_target` test was replaced with the published-and-reconciled proof. This is a durable-layer change staged for independent code review before final closure.

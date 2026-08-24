---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:edfd1dc0585cf1c40646885a24076e5b6a5eaf14859c57e5a31b8c63b22a052c'
step_id: 'S29'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Implement the resumable census executor across preflight, Clave device wait, remote read, proposal construction, interaction wait, exact apply, and settlement

## Scope

- `src/cadrumo/application/user_profile/_censal_operation.py`

## Description

- Define the strict censo operation request, result schema, phases, capabilities, and resumable definition.
- Refuse a foreign, inactive, or stale profile baseline before spending the operator's remote authentication.
- Acquire the read exactly once through the public live application seam, validate its taxpayer identity through the canonical reconciliation authority, and publish the complete encrypted reviewed operand.
- Resume only from the persisted checkpoint and secure operand, applying through `apply_cotejo` inside the supervisor irreversible section or settling rejection with no effect.
- Revalidate the stored baseline before the mutation window, retain `NONE` through irreversible-section entry, publish `UNKNOWN` only inside the protected section immediately before the writer, and narrow to `UPDATED` only after confirmed return.
- Expose only the executor's current authoritative revision so review publication can bind the exact successor transition after concurrent supervisor changes.
- Add strict request/definition and revision-protocol coverage beside the existing real encrypted operand and supervisor continuation proofs.
- Add composed races proving a competing real profile commit makes the reviewed CAS stale with `NONE` and no second event, while cancellation accepted before irreversible entry acknowledges with `NONE` and no profile write.

## Outcome

- One operation identity now spans preflight, Clave device wait, remote acquisition, durable review, response continuation, exact apply or reject, and truthful settlement phases.
- Initial execution never writes profile state; restart of either a pending review or consumed response never repeats the remote read.
- Proven stale state remains `NONE`, while an exception after entering the possibly committed write window can no longer publish a false no-effect receipt.
- A canonical stale compare-and-swap refusal raised by `apply_cotejo` is proven no-write and narrows the provisional effect back to `NONE` after leaving the irreversible section; every other exception retains `UNKNOWN`.
- Explicit field intents are complete and canonical before acquisition, while approval binds the frozen observation, profile identity, revision, content digest, and proposed effect.
- The definition declares resumable durability, exact approval, secure references, cooperative cancellation and deadlines, subject conflict exclusion, and only none, updated, or unknown effects.
- Real supervisor-backed race coverage proves the effect boundary stays truthful on stale compare-and-swap, pre-entry cancellation, confirmed apply, reject, and post-commit acknowledgement loss.
- Focused real secure-storage, exact-apply, and supervisor continuation tests passed, together with Ruff, BasedPyright, and diff-integrity checks on the owned surface.

## Notes

- The S113 context had no public way to name the interaction's exact successor revision. S29 adds a generic read-only `revision` property rather than exposing the persisted snapshot or coupling the executor to a private supervisor type.
- Public facade export remains the separately scheduled S32 step. The shared plan checkbox remains for the coordinating session.

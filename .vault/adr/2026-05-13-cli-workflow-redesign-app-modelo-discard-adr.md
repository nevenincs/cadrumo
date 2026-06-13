---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-work-units-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-calculate-revisions-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-apoderamientos-surface-research]]"
---


# `cli-workflow-redesign` adr: `App modelo discard work-unit verb` | (**status:** `accepted`)

## Problem Statement

The modelo lifecycle creates work units via `aeat app modelo create` and
calculation revisions via `aeat app modelo calculate`. When an operator
realises they created the work unit on the wrong active profile, or
abandoned a draft branch that will never be verified or filed, the
redesigned tree provides no operator-facing path to mark the work unit
abandoned. Orphan draft work units accumulate in the bucket with no
removal, contaminate `aeat app modelo list` output, and confuse status
reporting. This is the most-cited recovery gap from the gestoría
persona walkthrough.

## Considerations

- Calculation revisions in `verified_complete` or `filed` state are
  immutable; they must remain in the bucket as audit history regardless
  of operator intent.
- Draft revisions and the work units that own only draft revisions are
  mutable. They are the recoverable cohort.
- The bucket event history must record the abandonment so the audit
  trail explains why the work unit is no longer current.
- Deletion (physical row removal) is rejected; abandonment is a state
  transition, not a hard delete. Bucket event history depends on
  durable references.
- The verb name `discard` aligns with operator mental model ("throw this
  draft away"); `delete` is ambiguous against immutable revisions;
  `abandon` is acceptable as a synonym in help text but `discard` is the
  command name.

## Constraints

- `aeat app modelo discard` operates only on work units whose every
  calculation revision is in `draft` state. A work unit with any
  `verified_complete` or `filed` revision is rejected with a clear error
  pointing the operator to the filed-revision identity.
- The command transitions the work unit to `discarded` state and marks
  all draft revisions as `discarded`. Revision payloads are preserved
  for audit; only state changes.
- The command emits a `modelo.work_unit.discarded` bucket event with the
  work unit id, modelo, year, period, actor, optional reason, and the
  list of discarded revision ids.
- `aeat app modelo list` excludes `discarded` work units by default.
  `aeat app modelo list --include-discarded` shows them.
- A discarded work unit cannot be re-activated. A new work unit (with a
  new id) is required for any further work on the same modelo / year /
  period tuple.
- The command must be bucket-scoped through the active profile selected
  by `aeat config bucket`.
- The command must never submit, transmit, or live-file data with AEAT.

## Implementation

Command shape:

```text
aeat app modelo discard WORK_UNIT_ID --by ACTOR [--reason TEXT]
                                     [--format json|text]
```

The `--by ACTOR` flag follows the actor-attribution ADR (defaults to
active-profile display name; free-form label up to 64 chars).

State transition:

- Verify the work unit belongs to the active bucket.
- Verify every revision is in `draft` state; on any non-draft revision,
  emit a `CliValidationBoundaryError` naming the offending revision id
  and lifecycle state.
- Append a `modelo.work_unit.discarded` bucket event in the same logical
  transaction as the state mutation.
- Mark the work unit as `discarded` and mark every revision as
  `discarded`.

Output:

- Text: "Work unit WU_ID discarded (3 draft revisions). Reason:
  ..." with the active-profile header per §2 of the apex.
- JSON: envelope with `work_unit_id`, `state: "discarded"`,
  `discarded_revisions: [...]`, `actor`, `reason`, `event_id`,
  `bucket_id`.

## Rationale

Recovery from accidental wrong-profile creation is a real and frequent
operator scenario, especially for gestorías handling multiple clients.
Without a discard verb, the bucket accumulates draft contamination that
no operator command can clean. Treating discard as a state transition
(not a deletion) preserves the audit trail while letting operators move
on. Restricting to draft-only revisions protects the immutable lifecycle
guarantees of `verified_complete` and `filed` revisions.

## Consequences

- `aeat app modelo list` default-excludes `discarded` work units; the
  `--include-discarded` flag and `--state discarded` filter expose them.
- `aeat app modelo status` on a discarded work unit reports the
  discarded state with the discard event reference.
- The bucket event history surface (`aeat config bucket history`) renders
  `modelo.work_unit.discarded` events alongside other modelo lifecycle
  events.
- Tests must cover: discard succeeds on all-draft work units; discard
  refuses on any non-draft revision with a fix-pointing error; discarded
  work units are excluded from default `list` output; discard emits the
  expected bucket event; discard is bucket-scoped and respects the
  active-profile header contract.

---
tags:
  - '#adr'
  - '#tui-registry-api-gate'
date: '2026-09-24'
modified: '2026-09-24'
body_schema: 'body-v2'
body_hash: 'sha256:cef5b0a5eb15370ef20fc18c0f80f125fe3d26ec3b48eefc04144ec7150098b5'
related:
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
  - '[[2026-09-24-tui-registry-api-gate-corrupt-pointer-successor-reference]]'
---

# `tui-registry-api-gate` adr: `Successor revision for an active-profile pointer with no readable revision` | (**status:** `proposed`)

Proposed amendment to `2026-08-24-tui-registry-api-gate-adr`, section "Native WORK capture and registry separation". The accepted text stays in force until this is accepted; nothing below is applied yet.

## Problem Statement

The accepted decision makes the active-profile pointer's transition revision a durable monotonic coordinate: every successful write, restore or clear publishes exactly one successor, clear publishes an absent-selection tombstone instead of deleting the record, and a stale capture can never become current again. Every successor is computed as the observed predecessor plus one (`src/cadrumo/application/user_profile/profile_pointer.py:66`).

A present pointer record that does not decode, parse or validate is refused as `ActiveProfilePointerError` (`src/cadrumo/core/bucket_pointer.py:188`). The operator is routed to `aeat config repair profile --clear-active --yes`, whose clear is exactly such a successor write. With the predecessor unreadable there is no revision to add one to, so the accepted text admits no successor at all. Repairing a corrupt pointer therefore needs a rule the decision does not contain. Deleting the record instead would reset the coordinate to the cold-start zero (`src/cadrumo/core/bucket_pointer.py:202`), which is the regression the tombstone rule exists to prevent.

## Considerations

- Captures compare the pointer only within one process incarnation; the exposure is a long-lived process that captured the pointer before the corruption and re-reads it after the repair.
- Normal successors grow by one from zero, so live revisions stay small for the life of an install (`2026-09-24-tui-registry-api-gate-corrupt-pointer-successor-reference`, Producer).
- The stored field and its record bound hold a nanosecond seed (`2026-09-24-tui-registry-api-gate-corrupt-pointer-successor-reference`, Storage bounds).
- No reader assumes revisions are small or contiguous across a transition it did not observe (`2026-09-24-tui-registry-api-gate-corrupt-pointer-successor-reference`, Readers).
- Lower bounds can be salvaged from the handover and config-reset journals when they are present, and not otherwise (`2026-09-24-tui-registry-api-gate-corrupt-pointer-successor-reference`, Lower bounds that survive corruption).

## Considered options

- **Time-seeded successor (chosen).** Publish the tombstone at `max(time.time_ns(), salvaged lower bound + 1)`. Transitions after it continue at plus one. No schema change and no reader change. Residual risk: a wall-clock rollback that lands below a previous repair's seed.
- **Pointer epoch (rejected).** Mint a new epoch identity into the record at repair, and have captures compare the epoch as well as the revision. This satisfies the invariant with no clock assumption, but it changes the pointer schema, every pointer reader and writer, and every journal that embeds a pointer, all to serve a repair path that is rarely exercised.
- **No automatic clear (rejected).** Refuse permanently and tell the operator to delete the file. The next read then observes the cold-start zero, which violates the invariant more directly than either option above, and the recovery becomes an unsupervised file deletion.

## Constraints

- The pointer transaction remains the only writer and keeps its custody-root lock (`src/cadrumo/application/user_profile/profile_pointer.py:144`).
- The successor rule applies only when the predecessor is unreadable. A readable predecessor keeps the plus-one rule unchanged.
- The repair is reachable only through a command-spec declaration that observes a corrupt pointer as "no selection" for settings composition. The transaction keeps reading strictly, so it knows the predecessor is corrupt rather than absent.

## Implementation

- **Clear.** When `clear()` finds an unreadable predecessor, it publishes an absent tombstone at the seeded revision, where the seed is `max(time.time_ns(), salvaged lower bound + 1)`.
- **Lower bound.** Taken from the handover and config-reset journals when they carry a pointer.
- **Unchanged.** `select`, `compare_and_select` and `compare_and_restore` against a corrupt predecessor still refuse. Only the repair's clear may replace an unreadable record.
- **Tests:**
  - a corrupt pointer is replaced by a tombstone whose revision exceeds any salvaged bound;
  - the next selection publishes that revision plus one;
  - a readable predecessor still gets exactly plus one.
- **Before acceptance.** The repair refuses at the clear step with a typed manual-recovery refusal naming the file.

## Rationale

Knockout criterion: the rule must publish a successor that no capture taken before the corruption can equal, without a schema change for a rare path. Normal revisions grow by one per transition from zero, so a nanosecond wall-clock seed exceeds every revision a real install can have reached. The only way to publish a revision a live process has already captured is a clock set back below an earlier repair's seed. The epoch option closes that gap at the cost of a schema change across every pointer consumer. Refusing permanently hands the operator a deletion that resets the coordinate outright.

## Consequences

- A corrupt pointer becomes repairable through the supported command. The coordinate stays monotonic under any wall clock that does not move backwards past a previous repair.
- After a repair, revisions become large integers. Nothing reads them as counts, but a log or diagnostic that prints them will show the jump.
- The residual risk is stated, not eliminated: two repairs separated by a clock rollback larger than the time between them can reuse a seed. If that risk becomes material, the epoch option is the upgrade path. It would supersede this rule; it does not need to coexist with it.

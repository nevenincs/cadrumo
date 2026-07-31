---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:64397b6bd541aa998084725681493a6e5fde48fbfd245240e869ff16685b63dc'
step_id: 'S148'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Replace flat reset and legacy custody next actions with registered accepted commands

## Scope

- `src/cadrumo/core/errors/registry/_application_part1.py`

## Description

- Enumerate every command citation in the named error-registry module.
- Confirm no flat reset or legacy custody next action survives.

## Outcome

Every citation in the named module names a live accepted command. The custody and profile paths cite the accepted login, authentication, profile, and repair grammar, and no citation names a flat scoped reset or a retired custody verb such as rekey, lock, or show-recovery.

This is the surface the hand-sweep hazard warns about most directly, because a stale suggestion here is a dead operator instruction on an error path. It is covered: the suggestion-conformance gate resolves every registered error suggestion against the live command tree, so the citations cannot drift silently.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.

## Extended 2026-07-28

The record's claim held and still holds: no citation in this module names a
flat scoped reset or a retired custody verb. What it did not say is that the
reset lifecycle rows carried no citation at all.

Nine reset and journal rows had `default_suggestion=None`. That is invisible to
the hand-sweep hazard, because there is no stale verb to go dead, and equally
invisible to the suggestion gate, which resolves citations that exist rather
than requiring one. But these rows reuse generic shared message keys -- config
boundary, not-found, lock acquisition -- that name no command by design, so
with no suggestion the operator is told a reset failed and nothing about what
to run next.

Five now carry one. Already-running, operation-not-found, journal-not-found and
journal-already-exists resolve to `aeat config reset status`; an incomplete
journal resolves to `aeat config reset resume --yes`, the verb that rolls
exactly that journal forward. The generic boundary, corrupt-journal, ownership
and unconfirmed rows deliberately keep none: their next action depends on state
the error does not carry, and a confidently wrong instruction is worse than no
instruction.

Confirmed by mutation that the suggestion gate polices the new strings -- one
pointed at a non-existent reset verb fails with the file, line and unresolved
token.

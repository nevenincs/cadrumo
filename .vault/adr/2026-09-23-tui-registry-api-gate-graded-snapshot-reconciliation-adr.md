---
tags:
  - '#adr'
  - '#tui-registry-api-gate'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:9d301518790902632dbd1901c6a0a499550e7f467d38ab3f19e3961f49d46bb2'
related:
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
  - "[[2026-09-23-tui-registry-api-gate-graded-snapshot-restoration-reference]]"
  - "[[2026-08-24-tui-modelo-workspace-interface-adr]]"
  - "[[2026-09-04-reachability-burndown-adr]]"
  - '[[2026-08-26-tui-architecture-graded-snapshot-assembly-sizing-reference]]'
---

# `tui-registry-api-gate` adr: `reconcile graded admission to the current workspace contract` | (**status:** `proposed`)

## Problem Statement

The accepted API-gate decision defines graded-snapshot admission over eight
contributors, five capabilities and a second-pass currentness read. The
implementation was built to that contract, then deleted because no production
caller reached it. Later refactors removed the closure contributor, the
filing-export capability and the second-pass read, but the decision was never
amended (`2026-09-23-tui-registry-api-gate-graded-snapshot-restoration-reference`).
The TUI Results, Inputs and Verification destinations therefore render no
value: static inspection is the only admission, and it carries no work review,
materialization or readiness facet. Restoring graded admission requires the
contract it is restored against to be settled first. The decision leaves two
choices open that the launcher cannot make on its own: which grade to request,
and how to admit a unit that has no calculation.

## Considerations

- The closure contributor and the filing-export capability were removed by
  squashed bulk refactors with no recorded rationale. The current
  seven-contributor and four-capability contract is what every other consumer
  now builds on (`2026-09-23-tui-registry-api-gate-graded-snapshot-restoration-reference`).
- The second-pass currentness read was the API-gate decision's only defence
  against a baseline minted from contributors captured at different
  generations. Its removal also leaves static admission without that check.
- The accepted decision forbids downgrading a refused graded admission to
  static inspection (`2026-08-24-tui-registry-api-gate-adr`).
- The workspace interface decision requires the shared chrome to disclose the
  declared and required grades, and only a graded projection carries them
  (`2026-08-24-tui-modelo-workspace-interface-adr`).
- The reachability decision forbids symbol allowlists in gates, so a guard
  that graded admission stays reached must be behavioural
  (`2026-09-04-reachability-burndown-adr`).
- The old graded tests requested the calculation grade. That grade is what the
  materialization and verification facets the destinations render actually need.

## Considered options

- **Reconcile the contributor and capability sets, reinstate the currentness
  read, and restore graded admission with a production reader.** Kept. It
  matches the contract the rest of the code uses, restores the consistency
  guarantee, and ends the unreached-surface cycle.
- **Reinstate closure and filing-export as well, restoring the original
  eight and five.** Rejected. It would re-add surfaces with no current owner
  or producer, which the reachability decision would remove again.
- **Keep static inspection only, and populate the destinations from static
  captures.** Rejected. It would give static admission the calculation and
  readiness semantics the API-gate decision reserves for a grade-checked
  admission. That is the downgrade by another route.
- **Fall back to static inspection when graded admission refuses.** Rejected.
  The accepted decision forbids the downgrade, and the operator would see an
  empty destination with no stated reason.

## Constraints

- Canonical modules, the no-shim rule and the refusal models of the API-gate
  decision are unchanged (`2026-08-24-tui-registry-api-gate-adr`).
- The owner capture functions that fed the graded ports no longer exist and
  must be re-authored in their owner modules. Readiness has no public
  per-request producer today
  (`2026-09-23-tui-registry-api-gate-graded-snapshot-restoration-reference`).

## Implementation

This amends the API-gate decision in four places and leaves the rest of it in force.

- **Contributors.** Graded admission captures seven contributors: registry,
  work, bounded review, calculation, readiness, locale catalogue and field
  manifest. The closure contributor and its limbs are retired from the contract.
- **Capabilities.** Four capabilities remain, attributed as static admission
  now attributes them, with verification readiness owned by bounded review.
  Filing-export readiness is retired until a bucket-event producer exists; a
  later decision may re-add it.
- **Consistency.** The second-pass currentness read is reinstated for every
  admission, static and graded. Each contributor exposes a
  current-coordinate read beside its capture. A baseline is minted only when
  the second pass matches the first; a mismatch refuses with the existing
  changed or unavailable refusal, and never retries silently without limit.
- **TUI admission.** The TUI requests graded admission at the calculation
  grade for every work unit that has a current calculation revision.
  - A unit with no calculation is admitted by static inspection, and the
    chrome states that no calculation exists. This is a choice made before
    admission, from the work unit's own state, never a fallback after a graded
    refusal.
  - A graded refusal is shown as a refusal, with its reason and the action it
    names.
  - The launcher's reader type carries the refused result, so one refused
    unit does not refuse the whole Modelo source.

A behavioural test drives the production launcher reader over a calculated
unit and asserts that Results, Inputs and Verification render its values. A
second test asserts that a unit with no calculation is admitted by static
inspection and says so. The workspace field-population register loses every
entry the graded path now fills.

## Rationale

Reconciling to the current contract rather than the original one follows the
code that exists and the owners that produce it. Re-adding closure and
filing-export would recreate surfaces with no producer, and the reachability
gates would remove them again. Reinstating the currentness read is the
exception: it is the property that makes the baseline a single consistent
reading, not a surface, and its removal left no replacement. Choosing static
or graded before admission from the unit's own state keeps the no-downgrade
rule intact: a graded refusal is never converted into a static success.

## Consequences

- The destinations show the calculated values, the verification findings and
  the readiness axes for every calculated unit, with the grade disclosed in
  the chrome.
- Admission gains one currentness read per contributor, so it costs more; the
  sizing reference for graded assembly bounds that cost.
- Static admission also gains the currentness check it lost, so a static
  session can now refuse as changed where it previously read a mixed baseline.
- Filing-export readiness stays unmeasured in the chrome until its producer is
  decided.

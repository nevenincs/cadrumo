---
tags:
  - '#plan'
  - '#tui-registry-api-gate'
date: '2026-09-23'
tier: L1
related:
  - '[[2026-09-23-tui-registry-api-gate-graded-snapshot-reconciliation-adr]]'
  - '[[2026-08-24-tui-registry-api-gate-adr]]'
modified: '2026-09-30'
body_schema: body-v2
body_hash: 'sha256:2b8cdacdb98952c96a93bdea3d140dbef051dce517bcbc888514bdc479f5dc6b'
---

# `tui-registry-api-gate` plan

Restore graded snapshot admission so the TUI Results, Inputs and Verification destinations render a calculated unit's values.

## Description

Approved 2026-09-30. Basis: the operator, reviewing the sequence-backed TUI
captures, found every Modelo Results page refusing and every Verification page
empty, and authorized writing and executing the plan that feeds the work
review into the workspace. The same authorization accepted the reconciliation
decision, with its TUI-admission clause reconciled to the reader the TUI ships.

Graded snapshot admission was built, deleted as unreached because no
production caller reached it, and is restored here with its production
reader. It is restored against the current workspace contract as reconciled
by `2026-09-23-tui-registry-api-gate-graded-snapshot-reconciliation-adr`, an
accepted amendment of `2026-08-24-tui-registry-api-gate-adr`: seven
contributors, four capabilities, and a reinstated second-pass currentness read.
The grounding, including the contract changes the restoration must rebase over,
is `2026-09-23-tui-registry-api-gate-graded-snapshot-restoration-reference`.

Measured state at approval. The Modelo restoration merged on 2026-09-26
already restored graded assembly over six of the seven contributors, with the
calculation and readiness ports and the launcher's graded-first reader. The
seventh contributor, the bounded review, has an enum member and no port, so
the work-review facet is still declared unmeasured and the Results and
Verification destinations cannot render. No contributor runs a second-pass
currentness read. The Steps are scoped to that remainder.

Decision coverage: the reconciliation decision governs S01 through S06.
- S02 also changes static admission, which gains the currentness read.
- S05 carries the refusal arm as the reconciled TUI-admission clause states it.
- The API-gate decision's canonical modules, no-shim rule and refusal models
  govern every Step unchanged.

Acceptance evidence beyond the unit and behavioural tests is the
sequence-backed TUI review render: every scenario's Results and Verification
pages must show the calculated boxes and the review's findings.

## Steps

- [x] `S01` - Author the bounded-review capture and its current-coordinate read in the work-review owner module, with its not-current refusal key; the calculation and readiness captures landed with the graded restoration; `src/cadrumo/application/modelo/work_review.py`.
- [x] `S03` - Add the bounded-review workspace port on the current producer contract, beside the calculation and readiness ports already restored; `src/cadrumo/application/modelo/workspace_producers.py`.
- [x] `S04` - Assemble graded snapshot over all seven contributors so the work-review facet carries the canonical review, with work-review parity and capture-once conformance tests; `src/cadrumo/application/modelo/workspace.py`.
- [x] `S05` - Prove the launcher reader's graded-first admission carries every refusal to its destination, including the no-calculation refusal, and does not refuse the whole Modelo source; `src/cadrumo/entrypoints/tui/launcher.py`.
- [ ] `S06` - Prove through the production reader that Results, Inputs and Verification render a calculated unit's values, and re-render the sequence-backed review scenarios as acceptance evidence; `src/cadrumo/entrypoints/tui/modelo/view/tests/`.
- [ ] `S02` - Reinstate the second-pass currentness read for every workspace contributor, the bounded review included, and apply it to static admission; `src/cadrumo/application/modelo/workspace.py`.

## Parallelization

S01 precedes S03, because the port wraps the owner capture. S04 needs S03.
S05 needs S04. S06 needs S05. S02 runs last: its second pass covers all seven
contributors, the bounded review included, and it changes no rendered value,
so the operator-visible proof is not held behind it. Measurement at S04 showed
that the work, locale-catalogue and field-manifest owners define current
coordinates that nothing constructs, and calculation and readiness define none,
so S02 authors those owner reads before the second pass can use them. There is
no parallel execution; one writer owns the whole sequence.

## Verification

- Each owner capture has a test proving it captures exactly once, and one
  proving it refuses as not current after an interleaved write.
- A static or graded admission whose contributor moves between the passes
  refuses as changed.
- Graded conformance tests pass: a strict round trip, refusal ordering,
  work-review parity with `build_modelo_work_review`, readiness parity,
  provenance fan-out including unlinked sources, and a real-calculation
  assembly.
- A behavioural test drives the production launcher reader over a calculated
  unit and sees values on Results, Inputs and Verification. A unit with no
  calculation is admitted statically and says so. A graded refusal renders as
  a refusal and does not refuse the whole Modelo source.
- `just check-symbol-usage` reports no graded symbol as unreached, and the
  workspace field-population gate is green with the register reduced by the
  fields graded admission fills.
- The plan is complete when every Step is closed and the final integrated
  review passes.

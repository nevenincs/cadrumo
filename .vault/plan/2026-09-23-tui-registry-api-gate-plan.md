---
tags:
  - '#plan'
  - '#tui-registry-api-gate'
date: '2026-09-23'
tier: L1
related:
  - '[[2026-09-23-tui-registry-api-gate-graded-snapshot-reconciliation-adr]]'
  - '[[2026-08-24-tui-registry-api-gate-adr]]'
modified: '2026-09-23'
body_schema: body-v2
body_hash: 'sha256:c9a94f7a9d47eb6ed58125748c5080a84d1b41f628e2ca221fa09e8d3dcbdce5'
---

# `tui-registry-api-gate` plan

Restore graded snapshot admission so the TUI Results, Inputs and Verification destinations render a calculated unit's values.

## Description

Draft, not approved. No Step executes until the governing reconciliation
decision is accepted.

Graded snapshot admission was built, deleted as unreached because no
production caller reached it, and is restored here with its production
reader. It is restored against the current workspace contract as reconciled
by `2026-09-23-tui-registry-api-gate-graded-snapshot-reconciliation-adr`, a
proposed amendment of `2026-08-24-tui-registry-api-gate-adr`: seven
contributors, four capabilities, and a reinstated second-pass currentness read.
The grounding, including the contract changes the restoration must rebase over,
is `2026-09-23-tui-registry-api-gate-graded-snapshot-restoration-reference`.

Decision coverage: the reconciliation decision governs S01 through S05.
- S02 also changes static admission, which gains the currentness read.
- S05 carries the choice between graded and static admission, made from the
  work unit's own state, and the refusal arm.
- The API-gate decision's canonical modules, no-shim rule and refusal models
  govern every Step unchanged.

## Steps

- [ ] `S01` - Re-author the calculation, work-review and readiness capture and current-coordinate pairs in their owner modules, with their not-current refusal keys; `src/cadrumo/application/modelo/calculation.py`.
- [ ] `S02` - Reinstate the second-pass currentness read for every workspace contributor and apply it to static admission; `src/cadrumo/application/modelo/workspace_producers.py`.
- [ ] `S03` - Restore the calculation, bounded-review and readiness workspace ports on the current producer contract; `src/cadrumo/application/modelo/workspace_producers.py`.
- [ ] `S04` - Restore graded snapshot assembly over seven contributors and four capabilities, with its refusals, baseline and conformance tests; `src/cadrumo/application/modelo/workspace.py`.
- [ ] `S05` - Admit calculated units by graded snapshot and uncalculated units by static inspection in the launcher reader, carrying refusals and disclosing the grade; `src/cadrumo/entrypoints/tui/launcher.py`.
- [ ] `S06` - Prove through the production reader that Results, Inputs and Verification render a calculated unit's values, and retire the field-register entries the graded path fills; `src/cadrumo/entrypoints/tui/modelo/view/tests/`.

## Parallelization

S01 precedes S02 and S03, because the ports wrap the owner captures. S02 and
S03 both edit `workspace_producers.py`, so they are serial, with one writer. S04
needs S02 and S03. S05 needs S04. S06 needs S05. There is no parallel
execution; one writer owns the whole sequence.

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

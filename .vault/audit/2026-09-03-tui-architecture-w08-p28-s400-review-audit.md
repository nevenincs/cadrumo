---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_hash: 'sha256:5079a3ccd674bc1244a4338c61d46372bf90477b11a7c883d23ad33e31ac5b66'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
## Scope

Reviewed W08.P28.S400 in `application/workbench_generation.py`, its focused
application tests, the launcher generation adapter, and the installed child
entry path against the exact plan wording.

## Findings

### production-provider-absent | high | The child-owned provider does not compose production authorities

Open at initial review. `InstalledWorkbenchGenerationSourcesV1` was a collection
of callbacks already returning application inputs or projections. Neither it
nor the launcher bound secure profile repositories to canonical application
projectors.

### generation-capture-not-coherent | high | Independent sequential readers have no common capture proof

Open at initial review. Independent source callbacks carried no common bucket,
content digest, or repository revision proof.

### admission-projection-contradiction | high | The public generation accepts opposing route and source states

Open at initial review. The first contract revision checked destination names
but did not require source availability and route admission to agree.

### production-provider-resolved | low | Secure child generation provider is now concrete

Resolved. The launcher binds the live session's encrypted profile record,
Modelo work-unit, calculation-revision, and filing-record repositories into an
application-owned read door. The door emits canonical Declarations and calendar
projections. Ledger, Home subareas, AEAT Sync, and bulk Modelo authorities that
lack a coherent one-capture projector carry explicit unavailable reasons rather
than empty fixtures. Child-process bootstrap, same-registry operation
composition, production account composition, and Modelo editor composition are
owned downstream by S401 through S404 and are not claimed here.

### coherent-capture-resolved | low | Capture mutation and stale custody are refused

Resolved. The provider validates the live matching unsealed custody session at
both capture boundaries, refreshes the non-secret expiry fact, brackets the
profile content digest and all three catalogue revision tokens, and refuses a
generation if any authority changes during capture.

### admission-calendar-resolved | low | Admissions match sources and preserve calendar reachability

Resolved. Ledger, Declarations, and AEAT Sync admissions must exactly match
their source availability. An available or stale Declarations admission also
requires the calendar projection used by the real declarations screen factory.

### filing-evidence-scope-resolved | low | Historical filing facts remain truthful without orphaning the query

Resolved. A schedule-only legal query first establishes the current calendar's
natural address set. Only filing records addressed by that query enter the
local evidence projection; local source availability remains available even
when that measured query result is empty. A non-empty prior-year filing
regression proves it cannot abort the current-year generation.

### incomplete-schedule-resolved | low | Undeclared taxpayer facts cannot become an available empty schedule

Resolved. The canonical factless incomplete-profile path retains the safe
calendar projection for route reachability while its schedule source is
unavailable with `workbench.calendar.taxpayer_model_undeclared` and no
observation timestamp.

## Recommendations

Implement S401 through S404 before claiming normal child-process bootstrap,
same-registry operation contracts, production account affordances, or Modelo
editor composition. Do not widen S400's explicit unavailable sources until a
canonical one-capture application projector exists for each authority.

## Verification

Final focused result: 26 tests passed; the canonical incomplete-profile subset
passed in 64.56 seconds. Ruff lint and format checks passed. ty passed.
basedpyright reported zero errors, warnings, and notes. Targeted jscpd analyzed
one file for each owned production module and found zero clones. The canonical
unreachable-module ratchet passed, and exact scan output reports
`cadrumo.application.modelo.declarations_calendar`,
`cadrumo.application.workbench_generation`, and
`cadrumo.entrypoints.tui.launcher` reachable. Bare module execution printed
`workbench.root.composition_required` and returned 2. The independent final
scoped review returned APPROVE with no remaining S400-owned HIGH or CRITICAL
finding.

Final result: **APPROVE** for S400. Downstream S401-S404 dependencies remain
open and are not included in this approval.

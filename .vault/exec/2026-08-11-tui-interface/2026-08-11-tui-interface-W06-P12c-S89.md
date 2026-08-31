---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:b517a2ace36c2a5e68da3ad35c14f4724e3056e58897de9b9f82ae9a09a62b99'
step_id: 'S89'
related:
  - "[[2026-08-11-tui-interface-plan]]"
  - "[[2026-08-11-tui-interface-W06-P12c-S88]]"
---

# Prove every C4 candidate has a visible capability disposition, exact registered definition when mutating, declared interaction, terminal refresh mapping, action-specific locale and accessibility matrix, and no availability before its own proof is green

## Scope

- `src/cadrumo/entrypoints/tui/modelo/tests/test_c4_action_accessibility.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/modelo/tests/test_c4_action_accessibility.py`
- `verify:` `pytest test_c4_action_accessibility.py` -> `9 passed`

## Notes

THIS ROW PROVES WHAT NO PER-ACTION SUITE CAN. Each of the six enrolments
asserts its own action deeply; none of them can catch an action that was simply
never given a disposition, a definition, or a proof. So these checks run over
the dispatch table AS A CLOSED SET.

CAPABILITY DISPOSITIONS ARE VISIBLE, AND WHICH ONES ARE `None` IS ITSELF
PINNED. Every row either names the workspace capability gating it or explicitly
states that its availability is not a workspace-capability question. Asserting
only "a capability field exists" would be weak, so the capability-FREE set is
named exactly: {modelo.work.rename, modelo.work.discard}, both work-unit
lifecycle actions not gated by what a projection measured. Any OTHER action
answering `None` would be an ungated mutation wearing the same shape, and fails
here.

ONLY THE EDITOR APPLY DECLARES A MID-FLIGHT INTERACTION, measured rather than
assumed: all seven definitions were built and their `interaction_kinds` read.
`modelo.edit.apply` carries INPUT; the other six carry none. That is correct
and worth stating, because DISCARD looks like a counterexample -- it has an
exact-approval baseline. But that approval is carried IN THE REQUEST, formed
before submission, not asked for mid-run. Same for the file approval and the
amendment reason. Declaring an interaction an action does not have would leave
the modal waiting for input nobody will give.

NO ACTION IS AVAILABLE BEFORE ITS OWN PROOF EXISTS, checked structurally: every
enrolment module under `action/` must have a matching `test_c4_<name>_action.py`.
An action reachable from a surface with nothing asserting how it behaves is
available on the strength of nobody having checked it.

SCOPE CORRECTION ON THE ACCESSIBILITY MATRIX, recorded rather than quietly
narrowed. This row's text asks for an "action-specific locale and accessibility
matrix". The six C4 actions have NO per-action screens: they build typed
requests and present through the ONE shared `OperationModal`. A per-action
matrix would therefore be six copies of one surface's proof -- the duplication
this campaign removes everywhere else.

MEASURED GAP, which belongs to the shared modal rather than here: the modal's
own suites (`operations/tests/test_operation_modal.py` and
`test_operation_modal_lifecycle.py`) reference NONE of the shared accessibility
denominators -- no `SUPPORTED_TERMINAL_SIZES`, no `SUPPORTED_OUTPUT_LANGUAGES`,
no theme names. So the geometry/locale/theme matrix every C4 action depends on
does not exist anywhere yet. It is one matrix on one surface, and W06.P13.S93
(the C5 aggregate locale, geometry, theme and keyboard row) is where it
belongs. Building it here would put a shared surface's proof inside a
per-action row and leave S93 asserting it a second time.

WHY IT WAS NOT BUILT OPPORTUNISTICALLY ANYWAY: the modal's existing tests use a
REAL runtime -- real composed services, a real profile, a real submission, no
mocks, which is right. That path is currently KDF-dependent and was observed
failing with `KDF_SUPERVISION_UNAVAILABLE` during this session. A 4x4x2 matrix
stood up on it now would be heavy and environment-fragile, and a fragile matrix
teaches readers to ignore its failures.

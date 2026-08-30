---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:aef5437aa9d08468df6b861caf8e23916a9494241243efb0e1e4497fecd42d7c'
step_id: 'S357'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Carry the resolved target into refusals that hold one, judging each construction rather than sweeping all three. Verified: three refusal constructions pass selected_target=None. THEY ARE NOT EQUIVALENT AND A UNIFORM FIX WOULD BE WRONG. The TARGET_NOT_FOUND construction sits inside the branch reached BECAUSE the work unit is None, so passing None there is honest and must stay. The CALCULATION_UNAVAILABLE construction sits immediately AFTER that guard, in a branch where work_unit is provably not None and its revision id is merely absent -- so it drops a target it is holding, and tells an operator there is no calculation without saying for which unit. The third construction needs the same judgement applied before it is changed. Refusals are where an address matters most, which is what makes this worth fixing rather than tidy

## Scope

- `src/cadrumo/application/modelo/workspace.py`
- `the three domain refusal constructions`

## Changes

- `M` `src/cadrumo/application/modelo/workspace.py`
- `M` `src/cadrumo/application/modelo/tests/test_workspace.py`
- `verify:` `pytest test_workspace.py -k "refus or unavailable"` -> `7 passed`
- `verify:` `pytest ...refuses_when_the_target_has_no_calculation` -> `1 passed`
- `verify:` `bite proof over the real fact types` -> `wrong id -> AssertionError; no facts (pre-change state) -> KeyError; foreign fact -> KeyError`

## Notes

THE ROW'S PREMISE FOR THE SECOND CONSTRUCTION IS WRONG AND selected_target=None
IS CORRECT AT ALL THREE SITES. The CALCULATION_UNAVAILABLE refusal does not
hold a resolved target it drops. `ModeloWorkspaceResolvedTargetV1` requires a
law_selected_revision_id, a review_status and both revision assertions, and all
four come from the REGISTRY capture, which runs AFTER this guard. Reaching a
target here needs one of two forbidden moves: relocating the guard past
registry admission, which `test_resolve_graded_snapshot_result_refuses_when_
the_target_has_no_calculation` pins by name and docstring; or feeding the
stored revision id back as the selector, which the revision-resolution rule
prohibits as the defect class that computes one year under another year's norms.

The operator complaint underneath the row is real and is now answered: the
refusal said there was no calculation without saying for WHICH unit. The work
unit identity travels as a typed `ModeloWorkspaceEvidenceFactV1`, which is the
FIRST production construction of that vocabulary -- decision D7 of the
modelo-workspace-interface ADR mandates evidence on refusals, and until now
nothing built one. This narrows W03.P20.S353's remaining scope by the same
mechanism.

The added assertion compares against the independently derived work unit id
rather than asserting presence, because a fact carrying the WRONG unit reads
exactly like a correct one.

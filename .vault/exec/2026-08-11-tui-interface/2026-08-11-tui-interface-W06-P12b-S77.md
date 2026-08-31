---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:b2e5affb1327926ac8f3530cc740880951b9c27ca841778b43fc6979496328e8'
step_id: 'S77'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Submit only normalized ModeloEditSubmissionV1 through the public operation-owned financial handoff, fold public observation to settlement, resolve only the typed Workspace refresh target, and enter stale conflict without merge, rebase, result-ref interpretation, or old-view patching

## Scope

- `src/cadrumo/entrypoints/tui/modelo/edit/controller.py`

## Changes

- `M` `src/cadrumo/entrypoints/tui/modelo/edit/controller.py`
- `M` `src/cadrumo/application/modelo/edit_session.py`
- `M` `src/cadrumo/entrypoints/tui/modelo/edit/tests/test_controller.py`
- `verify:` `pytest edit package + c3 accessibility + edit_session` -> `34 passed`

## Notes

PARTIAL: the stale-conflict clause is delivered; the submission clauses are not.
Submitting through the operation-owned financial handoff and folding public
observation to settlement require the operations platform -- an async supervisor
submission of the kind W07.P16.S340 also needs -- which is different engineering
from the editor surface and is not started here.

STALE CONFLICT RESCUES NOTHING, WHICH IS THE POINT. The row forbids merge,
rebase, result-ref interpretation and old-view patching. Each would produce a
screen that is neither what the operator wrote nor what the tree holds, and then
submit that. `refresh` reports which coordinates drifted and moves nothing: the
staged edits stay staged and the baseline they are judged against stays put, so
a submit still refuses against the coordinate it was admitted on.

A DEFECT OF MY OWN, FOUND BY A FAILING TEST AND NOT BY REVIEW. The first version
answered staleness by comparing two admission RECORDS. An admission carries its
own identity and lifetime -- `baseline_id`, `issued_at`, `expires_at` -- so two
admissions of an UNCHANGED tree are never equal, and the signal was stuck
permanently on 'stale'. A gate that always fires is as useless as one that never
does, and worse: it teaches the operator to ignore it.

Corrected to ask `reconfirm_modelo_edit_baseline`, the contract's own
compare-and-swap, which judges the coordinate axes the guarded commit point
judges. That is the SAME one-authority correction made earlier the same day to
the work-target revision comparison. Writing that lesson down did not prevent
repeating it hours later; the test did.

CONSEQUENCE, and it invalidated a claim already recorded: with staleness moved
to the CAS, the session's second 'read' baseline had nothing left to do -- set
at open, never read. It was removed, and W06.P12b.S72's record was amended,
because a closed row asserting a shape the code no longer has is precisely the
stale artefact this campaign keeps finding in other rows.

The new tests carry the control the first one lacked: an unchanged tree must
report NO drift and an emptied catalogue must report drift. The original
asserted only the first and would have passed against a `refresh` that did
nothing at all.

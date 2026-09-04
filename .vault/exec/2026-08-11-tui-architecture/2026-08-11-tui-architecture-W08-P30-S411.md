---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:9896fbffa3facae8b203b1c28d6390d42a94fa1b602ea53fcc0e9da060216223'
step_id: 'S411'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Carry an operator's Ledger selection into the areas that are entered with one. CORRECTED AFTER MEASURING THE REFUSAL RULES, which the first wording got wrong in two ways. It is THREE areas, not four: reconciliation has no door check and is reachable whenever the projection admits it. And of the three, only EVIDENCE was a composition gap -- now closed, the installed factory binds the evidence action and reads the attachment review queue. CLASSIFICATION and IMPORT are not composition gaps at all: classification refuses without a selected transaction and import without a prepared file, and neither is a fact a factory can hold at mount because both are produced by the operator inside the workspace. So what remains is NAVIGATION, not wiring: the entries and review screens must be able to carry a chosen row into the classification area, and the import action must be able to hand a prepared import back to its own area, with the controller re-composed around that state. Until that exists the two areas are correctly refused, and the navigation table should say why rather than listing a destination the session can never open.

## Scope

- `src/cadrumo/entrypoints/tui/ledger/controller.py and src/cadrumo/entrypoints/tui/ledger/routes.py`

## Changes

- `M` `src/cadrumo/entrypoints/tui/ledger/controller.py`
- `M` `src/cadrumo/entrypoints/tui/ledger/tests/test_ledger_flows.py`
- `verify:` `pytest -n0 -m '' src/cadrumo/entrypoints/tui/ledger/tests` -> `pass` (78)

## Notes

Step left OPEN: classification navigation is closed, import is not.

CLASSIFICATION. `LedgerEntrySelected` was posted by the entries screen and
handled by nobody, so the operator's choice went nowhere. Classification
refuses without a `classification_target`, and that target was bound when the
workspace was COMPOSED -- before the operator had chosen anything -- so in a
real session the area was permanently refused while the navigation table went
on listing it as a destination.

`select_classification_target` now carries the chosen row, checked against the
VISIBLE projection using the same invariant the constructor enforces: a target
the current snapshot does not contain would open classification on a row the
operator cannot see, which is worse than the refusal it replaces. The handler
lives on the shared screen base rather than on the entries screen alone,
because the review screen names the same selection and both feed the one area
entered WITH a row, and it repaints the navigation table so the destination
stops reading as refused the moment it becomes reachable -- an operator who
selects a row and sees nothing change cannot tell whether the selection
registered.

The gate went into `test_ledger_flows.py` rather than beside the entries tests,
because every test there binds `classification_target` up front and THAT is the
workaround which hid this for so long. With the doors bound and the target
absent, the selection is the only variable. The refusal is asserted before and
its absence after: either half alone proves nothing, since a screen that always
admits classification passes the second and one that never does passes the
first. A second gate proves the visibility check refuses an id outside the
snapshot. Teeth proven by dropping the selection in the handler.

IMPORT is untouched, and measuring it shows why it is a different KIND of gap
from the classification one -- which is worth stating, because the step's
wording assumes otherwise.

The step says "the import action must be able to hand a prepared import back to
its own area". There is no import action. The operator action catalogue
declares five ledger actions -- link, evidence.review.list, classify, review,
preflight -- and no import among its thirty-eight entries. So the premise is
unmet before any navigation question arises.

`LedgerPreparedImportV1` is likewise constructed nowhere in production: only in
two test modules. And the service beneath it, `import_ledger_source`, takes a
`LedgerSourceImportCommand` carrying a filesystem PATH. The TUI has no
path-entry or file-selection surface, so there is nothing an operator can do
inside the workspace that would produce a prepared import.

That makes this a missing CAPABILITY, not a navigation gap: it needs a
path-entry flow, an action catalogue entry, and a producer, before "carry it
back to its area" becomes a meaningful sentence. Unlike the four labels in this
campaign that dissolved on measurement, this one was verified in three
independent ways -- no catalogue entry, no production constructor, and an
underlying service requiring an input the TUI cannot obtain.

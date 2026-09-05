---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:29c8a107760407289194fdfe39d843859318e23e6e2ccd8452ab0d4712dd771b'
step_id: 'S411'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Carry an operator's Ledger selection into the areas that are entered with one. CORRECTED AFTER MEASURING THE REFUSAL RULES, which the first wording got wrong in two ways. It is THREE areas, not four: reconciliation has no door check and is reachable whenever the projection admits it. And of the three, only EVIDENCE was a composition gap -- now closed, the installed factory binds the evidence action and reads the attachment review queue. CLASSIFICATION and IMPORT are not composition gaps at all: classification refuses without a selected transaction and import without a prepared file, and neither is a fact a factory can hold at mount because both are produced by the operator inside the workspace. So what remains is NAVIGATION, not wiring: the entries and review screens must be able to carry a chosen row into the classification area, and the import action must be able to hand a prepared import back to its own area, with the controller re-composed around that state. Until that exists the two areas are correctly refused, and the navigation table should say why rather than listing a destination the session can never open.

## S14 corrective quarantine (2026-09-05)

The import-preparation operator reachability work recorded below was removed from production because this row remains `DISPLACED_AND_HELD_UNTIL_G3`. The prior IMPORT `CLOSED` claim is therefore superseded: there is no Overview path-entry route, controller admission, installed import submitter, import operator action, or TUI-only producer/coverage. The canonical application validator at `application/ledger/import_preparation.py` and its direct application tests remain backend-only. This record does not authorize reimplementation; clitui-ledger remains the sole owner through W05.P21.S136, with W05.P19.S128 as the disposition checkpoint.

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

IMPORT: two of its three missing pieces now exist. Original measurement kept
below, because it is what scoped the work.

`operator.ledger.import` is in the operator action catalogue, targeting the
real `ledger.import` command identity. It declares NO arguments: the source
path rides inside the sealed command the operator prepared, never as a
catalogue argument, so a filesystem path cannot reach an action record or
anything that renders one.

`prepare_ledger_import` is the producer that did not exist. It turns an entered
path into a `LedgerPreparedImportV1`, refusing a blank entry, an absent path, a
directory or an unreadable file BEFORE any provider work -- `import_ledger_source`
would refuse an unreadable source too, but by then the operator has left the
screen and the refusal arrives detached from the entry that caused it. The
provider resolves as `auto`, the detection the import service already performs;
asking an operator to name the bank format of a file they just chose is asking
them to do the parser's job.

The path never escapes the sealed command. `LedgerPreparedImportV1` keeps it in
a weak-keyed vault with no attribute, repr or serialization surface, and the
gate asserts the path, its PARENT and its filename are all absent from
everything the object exposes -- a directory alone identifies a machine and a
person. Refusal messages name which condition failed and never the path, so a
refusal cannot leak what a success hides.

Teeth proven by naming the path in a refusal; the gate fails on the message
text. 6 passed on the producer, 49 on the operator-action catalogue.

The path-entry surface exists too, and the import area is now enterable. It
lives on the Ledger OVERVIEW screen, not on the import screen: that screen
refuses without a prepared import, so an entry inside it could never be
reached. Preparing one from the overview is what makes the destination
admissible -- the same shape as selecting an entry to admit classification --
and `accept_prepared_import` refuses a duplicate choice id rather than
shadowing an earlier preparation, since two rows sharing an id would leave the
selected row not determining the command that runs.

AN ARCHITECTURE GATE CAUGHT A REAL VIOLATION AND I MOVED THE CODE RATHER THAN
THE GATE. `test_ledger_tui_has_no_io_adapter_cli_calculation_or_mutation_imports`
failed on the first draft: the path validation used `exists`, `is_file` and
`open` INSIDE the TUI package, which is adapter work in a presentation layer.
The validation now lives in `application/ledger/import_preparation.py`, where
filesystem access belongs and where it mirrors `import_ledger_source`'s own
pre-provider guard; the TUI module only seals the resulting command behind its
display identities. The split is not bookkeeping -- the gate exists precisely
to stop presentation code touching the disk.

Teeth proven twice on the surface: dropping the acceptance leaves the area
refused (`the operator prepared an import and the area is still refused`), and
echoing the entry into the status line fails the path-free assertion. 96 passed
across the ledger suites.

The original measurement, kept because it scoped this work:
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

CLOSED. The doors are bound, which was the last gap and one the earlier passes
had not noticed: navigation admitted classification and import, but the
INSTALLED factory bound only the review and evidence doors, so a live session
still refused both with `submission_unavailable`. Two areas can be reached only
because all three of action, target and submitter are now present.

`operator.ledger.classify` and `operator.ledger.import` join the session's
action set. The import submitter forwards an already-sealed command to
`import_ledger_source`, so the door never sees a path the presentation layer
chose. The classification submitter applies the patch through
`update_manual_transaction_fields` and passes the CATALOGUE action id as the
source command rather than a bare "tui" label -- an amended classification that
cannot say which authority it was made under is an audit gap in a filing-bound
record.

One kwarg was written and removed rather than left: `import_action` is not part
of `ledger_screen_factory`'s surface, and adding a parameter nothing consumes
to make a call site read symmetrically would have been invented API. The
dependency was dropped with it.

91 passed across the ledger and installed-entrypoint suites.

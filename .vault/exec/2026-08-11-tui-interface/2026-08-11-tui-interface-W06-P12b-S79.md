---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:080a00e9012ded8598d12845170ca6c93685f7e672b568dc09502ebb5eb9dada'
step_id: 'S79'
related:
  - "[[2026-08-11-tui-interface-plan]]"
  - "[[2026-08-11-tui-interface-W06-P12a-S71]]"
---

# Prove the C3 editor state machine, parse and validation focus, review-only submit, stale refusal, atomic-result refresh, locale switch, operation handoff and sensitive non-retention green on current source, then record the C3 exit governance fact as an execution record wiki-linking the C3 prerequisite record; `src/cadrumo/entrypoints/tui/modelo/tests/ C3 editor conformance modules and .vault/exec/2026-08-11-tui-interface/2026-08-11-tui-interface-W06-P12b-S79.md`. CHAIN DEPENDENCY, MEASURED 2026-08-31, AND THIS ROW IS NOT THE NEXT STEP IT APPEARS TO BE. Its link target is S71's record, which does not exist; S71 in turn must link S59's, which does not exist; S59 must link S49's, which does not exist. Four levels down to a root that was never written. Approached row by row -- which is how a plan invites you to work -- this reads as the ordinary successor to S78, and the chain is rediscovered one blocked row at a time. THE PROVING HALF IS ALREADY SATISFIED and is not what blocks this row: S78 closed 2026-08-31 at 36 passed / 0 failed covering all eleven axes, including the three that needed the mounted screen built for it (lexical-error focus, terminal refresh, the accessibility matrix). What remains here is purely the record, and it must not be written until S71's record resolves -- a governance artifact citing a name that does not exist is precisely the failure the chain exists to prevent.

## Scope

- `src/cadrumo/entrypoints/tui/modelo/tests/ C3 editor conformance modules and .vault/exec/2026-08-11-tui-interface/2026-08-11-tui-interface-W06-P12b-S79.md`

## Changes

- `A` `.vault/exec/2026-08-11-tui-interface/2026-08-11-tui-interface-W06-P12b-S79.md`
- `verify:` `pytest edit/ test_c3_editor_screen.py test_c3_editor_accessibility.py test_edit_session.py test_edit_wire_submission_mirror.py` -> `51 passed`

## Notes

THE C3 EXIT FACT. The C3 editor state machine, parse and validation focus,
review-only submit, stale refusal, atomic-result refresh, locale switch,
operation handoff and sensitive non-retention are proven by the editor package
`entrypoints/tui/modelo/edit/`, the mounted-surface suite
`test_c3_editor_screen.py`, the adversarial suite
`test_c3_editor_accessibility.py`, and the application-side
`test_edit_session.py` and `test_edit_wire_submission_mirror.py`. Run
2026-08-31: 51 passed, 0 failed. HEAD was
`35c1721dd88e13402506b7e56863821cced75c8f`; THE RUN WAS AGAINST THE WORKING TREE
AT THAT HEAD, NOT A CLEAN CHECKOUT, as with every record in this chain.

WHAT THE C3 BUILD ACTUALLY PRODUCED, beyond the passing count.

OPERATION HANDOFF EXISTED ONLY ON PAPER. The registered `modelo.edit.apply`
operation had NO production caller: `ModeloEditApplySubmissionV1` owned
`to_submission` (wire to domain, which the executor needs) but not its inverse,
and the single site constructing the wire type was a test. The editor could
stage edits with nowhere to send them. The inverse now lives beside
`to_submission` so the two directions cannot drift, with a shared
`_WireDetailRowMirror.from_row` serving all six per-modelo mirrors -- the
direction back does not differ between them, only `Decimal` becoming its exact
characters -- reached through a `row_type`-discriminated dispatch rather than a
hand-written map that could fall behind the union.

THE DETAIL-ROW ASYMMETRY IS PERMANENT AND DELIBERATE. A domain detail-row
address carries only the JOINED natural key; the wire form carries the identity
components. Splitting the key back apart cannot be made correct, because a
component containing the separator is indistinguishable from a boundary once
joined -- it would guess right for most rows and wrong for exactly the rows whose
identifier contains the separator, producing a misaddressed edit rather than an
error. So `from_submission` refuses detail rows, and only the session, which
captured the components at staging time, may build that address.

THE LOCALE DEFECT IS THE MOST IMPORTANT THING HERE, and it was invisible until
a screen existed. The editor renders through ambient `tr()` while the controller
parses lexemes in the locale it was ADMITTED for, and nothing kept them in step:
an operator could be shown Hungarian while their number was parsed as Spanish.
`1.234,56` is a valid spelling in more than one language, so the form accepts
the typing and RECORDS A DIFFERENT AMOUNT THAN THE OPERATOR BELIEVES THEY
ENTERED, with no error for anyone to notice. Every headless proof passed
throughout, because none of them had a display language to disagree with. The
screen now refuses to mount on a divergence -- raised rather than surfaced as a
notice, since a mismatch means the route was built with the wrong locale, a
programming error the operator cannot act on.

TWO DEFECTS IN THIS COHORT'S OWN EARLIER CODE, both found by changing it rather
than by reading it: `stage_row` accepted the natural key BESIDE the row, so an
address and the row it described could disagree while the contract addresses by
key; and correcting that immediately exposed a test asserting the key
`DE123456789` when the row's real compound key is `DE123456789|E` -- an address
no row ever had.

STANDING GOAL NOT COVERED: this record's predecessor relationship to the C3
prerequisite record is a wiki-link, which is a human-checked claim. Nothing
recomputes it, and nothing fails if that predecessor later goes red.

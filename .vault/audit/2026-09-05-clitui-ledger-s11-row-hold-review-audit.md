---
tags:
  - '#audit'
  - '#clitui-ledger'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:3f0788eed964557ba9b7d1765d6400782908b14a87c388a6da5df76811c8f7b4'
related:
  - "[[2026-09-04-clitui-ledger-plan]]"
  - "[[2026-09-04-clitui-ledger-reference]]"
  - "[[2026-09-04-clitui-ledger-W01-P03-S11]]"
---

# `clitui-ledger` audit: `S11 row-level TUI hold review`

## Scope

Reviewed S11's schema-v3 union and complete matrix row holds, hold mutation
tests, gate predicates, current reference, plan, execution record, generated
index, and the five named commits. Vaultspec-RAG was attempted first; its local
code index was empty, so exact source reads, independent projection execution,
and focused/full test runs supplied the evidence.

## Findings

**Ruling: NOT ACCEPTED.** One HIGH finding remains.

The independent projection reproduces 760 observations, 769 selected edges,
693 rows, and
`sha256:6d4f8685359271136a8fdba99c84ed238bc3a3daec03b3ca55c2d671d74ab2a4`.
Exactly 680 TUI-applicable rows carry only
`g3_cli_clean_break_and_completeness`; the 13 TUI-not-applicable rows are
unheld. Union and complete matrix row validators reject missing, extra, or
alternate-gate holds, including after aggregate digest refresh. The embedded
TUI census remains one installed Overview and six component-only routes. G0
is OPEN, S11 is checked, and the named commits introduce no production TUI
implementation.

### gate-lifecycle-cannot-authorize-the-hold-lift | high | Individual G4 closes prematurely while ordered G4 can never close after a lift

`evaluate_ledger_capability_gate` evaluates G4 without any accepted-G3 state.
A matrix with a manually inactive hold and otherwise complete TUI evidence can
therefore close G4 even while the same matrix fails G0 because G0 always
requires the hold active. The committed
`test_valid_controls_close_g0_through_g3_and_lifted_hold_closes_g4` explicitly
asserts that contradictory result: G0 open and individual G4 closed.

The ordered evaluator avoids that premature closure only by re-evaluating G0.
Once the hold is legitimately lifted after G3, G0 necessarily becomes open and
the ordered evaluator marks every later gate closed=false. Thus there is no
typed state that both proves G3 was accepted and permits the ordered G4
predicate to close. The row's `tui_hold_until=G3` describes the boundary but
does not authenticate that the boundary was crossed.

## Recommendations

- Add a typed, digest-bound accepted-gate closure record or receipt to the
  campaign state. An inactive global hold must be valid only with an accepted
  G3 receipt bound to the current denominator/matrix revision.
- Require G4 to validate that G3 receipt. Make ordered evaluation preserve
  accepted prior gates while still reopening them on currentness or denominator
  drift, rather than re-failing G0 solely because the duly authorized hold was
  lifted.
- Add tests proving premature hold lift/G4 refusal before accepted G3,
  successful ordered G4 after an accepted current G3, and re-locking after
  receipt or denominator drift.

## Verification

The independent projection reproduced the exact count, hold, digest, and TUI
reachability facts above. The full matrix module passes all 222 tests. Ruff
format/check, scoped `ty`, and feature Vault checks pass. Green
hold-serialization tests do not resolve the gate-lifecycle contradiction.

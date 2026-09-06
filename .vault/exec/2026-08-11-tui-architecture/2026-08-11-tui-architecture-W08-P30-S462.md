---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:4fca43a434482d6a42afd0584f167da90ca05f394d773c4860e295e3ab905a9c'
step_id: 'S462'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Repair the generated casilla reference key derivation that silently enumerated nothing after three closed fields became enums, since get_args answers for a Literal and returns empty for an Enum so the families vanished from the declaration while the surface kept rendering them and twenty-six shipped keys were reported as stale copy

## Scope

- `dev/docs/casilla_reference.py`
- `dev/docs/tests/test_casilla_reference_presentation.py`

## Changes

Parity extras: 167 -> 141. The `docs.*` group went from 26 to ZERO, and not one
of those keys was stale.

A REAL DEFECT, not another scanner widening. `display_locale_keys` derives the
enum-backed families from the schema's own closed value sets, and its docstring
states the guarantee that buys: adding a member "immediately demands its string
instead of rendering nothing". It read `get_args`, which answers for
`Literal["money", ...]` and returns an EMPTY TUPLE for an `Enum`.

All three fields it asks about -- `CasillaDefinition.data_type`,
`ModeloDefinition.cadence`, `CasillaConstraints.sign` -- have since become
enums. So the guarantee had inverted. The families disappeared from the
declaration while `_render_fill` went on rendering
`docs.casilla.data_type.{record.data_type}` on every casilla page, and the 26
shipped keys behind them were reported as stale copy on that basis.

Nothing about the failure was visible: an empty family and a family with no
members are indistinguishable downstream. So the repaired function now RAISES
on a field it cannot enumerate rather than returning empty -- silence is the
exact defect, and a family that yields nothing is never a fact this derivation
is entitled to assert.

Teeth: restoring the `get_args`-only read -- the original bug verbatim -- fails
the new gate, which asserts the families are PRESENT rather than merely that
the call succeeds. Restored by copy.

## Notes

THIS IS THE SIXTH TIME IN THIS CAMPAIGN that "no literal found" turned out to
mean "the tooling could not see a live call", and the first where the blind
spot was in a live generator rather than in the scanner. It is the standing
argument against pruning the residue on absence of evidence.

TARGET 2 REMAINS OPEN at 141 extras: 125 `cli.*`, 11 `tui.*`, 5 `application.*`.
The suite reports the parity gate alone; the docs presentation suite is green,
and the shadow gate no longer appears in this selection because the run did not
include it.

The `cli.*` 125 carry the S461 evidence: the live command-spec registry
declares none of them, and the live command tree has no `config init` or
`config get`. That decision is the operator's.

Two of the 11 `tui.*` extras are
`tui.ledger.reconciliation.direction_state.invoice_only` and
`.transaction_only` -- the catalogue side of the blocked `direction` collision.
They are extras for exactly the reason the other two keys are missing: the code
was reverted to `direction.*` and the catalogue kept `direction_state.*`. One
decision resolves both halves.

Residue: 8 full-literal, 35 tail-only, 98 no-trace.

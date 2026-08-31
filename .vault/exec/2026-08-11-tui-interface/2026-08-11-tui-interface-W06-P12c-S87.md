---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:d3aac31de5387bee3325cfd39ff27149f0e800744e82d96637fd8d2ec59bd57a'
step_id: 'S87'
related:
  - "[[2026-08-11-tui-interface-plan]]"
  - "[[2026-08-11-tui-interface-W06-P12c-S86]]"
---

# Enroll modelo.work.amend as a distinct C4 amendment mode and atomically replace the amend-wizard TUI capability or classify that transitional row DEFERRED with owner, evidence, and reopening gate

## Scope

- `src/cadrumo/entrypoints/tui/modelo/tests/test_c4_amend_action.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/modelo/action/amend.py`
- `A` `src/cadrumo/entrypoints/tui/modelo/tests/test_c4_amend_action.py`
- `verify:` `pytest test_c4_amend_action.py` -> `10 passed`

## Notes

AMENDMENT IS THE ONLY ACTION IN THIS COHORT ADDRESSED TO SOMETHING ALREADY
FILED, and everything distinctive follows from that. It is keyed on the FILING
RECORD rather than a work unit, so two amendments of the same filed return
contend: they describe competing corrections to one declaration. Keying the
subject on a work unit would let them proceed concurrently and the authority
would receive two corrections with no established order.

THREE CONTRACT REQUIREMENTS NO SIBLING HAS, each carried through rather than
softened. A REASON IS MANDATORY -- discard's is optional because abandoning
local work owes nobody an explanation, while telling the tax authority a filed
figure was wrong does; the asymmetry is deliberate, not an inconsistency. AT
LEAST ONE OVERRIDE -- re-filing identical numbers would tell the authority a
figure changed when none did. VALUES CROSS AS EXACT CHARACTERS -- the override
value is a pattern-checked string rather than a `Decimal`, because a `Decimal`
accepts number-or-string and emits string, so a journalled request would not
round-trip to what the operator typed. On a correction to a filed return the
digits are the whole content.

OVERRIDES ARRIVE AS A MAPPING so the same casilla cannot be corrected twice
with different values. A sequence would admit that contradiction and leave the
contract to decide which one counted; a mapping makes it unrepresentable.

THE ROW'S SECOND HALF NEEDED NO ACTION, and the reasoning is recorded rather
than the conclusion alone. `modelo.work.amend_wizard` is a DIFFERENT action
from `modelo.work.amend`, already classified FLOW_OWNED with an owning
authority (tui-architecture guided flows), a stated reason, an evidence
reference, and a reopening condition reading "reopens only if C4 assigns this
wizard a distinct disposition". Enrolling `modelo.work.amend` assigns the
WIZARD nothing, so that gate stays shut. Reclassifying it DEFERRED would also
LOSE information: FLOW_OWNED is the more specific disposition and matches the
accepted ADR framing the denominator cites, whereas DEFERRED means owned
entirely outside this plan. A test pins that the wizard is absent from the
dispatch table, so this row cannot be read as having replaced a surface it
never touched.

A THIRD IMPORT GUESS OF MINE, CORRECTED: `CalculationRevisionAmendmentKind` and
`M303RectificativaMotive` live in
`domain/modelos/calculation_revision_amendment.py`, not the `core` paths
assumed. Like the election enums in W06.P12c.S85, these sat under TYPE_CHECKING
and so would have failed silently at runtime -- only a real import surfaces
them.

WITH THIS ROW ALL SIX PER-ACTION ENROLMENTS ARE COMPLETE: rename, discard,
verify, file, export and amend. Each submits through the composed supervisor,
none reaches a writer directly, and each pins a different half of the
platform's contract -- whitespace stripping versus identifier exactness,
cancellation supported versus unsupported, replay safety, the prohibition on
live submission, journal confidentiality, and now filed-record addressing.

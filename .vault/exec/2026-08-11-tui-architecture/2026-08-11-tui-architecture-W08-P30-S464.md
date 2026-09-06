---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:a3e8be79165d2544002fee92e5d425a47f1eacc71c24c03e7672dd87dce8cec2'
step_id: 'S464'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Read the key a surface names in a local before rendering it, admitting only a string constant or a conditional between them so the rule cannot claim the registry and row-table shapes it does not confirm, and requiring the name to reach a translator so a route held the same way stays out

## Scope

- `dev/locales/_ast_scanner.py`
- `dev/locales/tests/test_dynamic_prefix_registry_coverage.py`

## Changes

Parity extras: 140 -> 138. Full-literal residue 7 -> 5.

BLIND SPOT 12. A surface picking between two labels names the choice before
rendering it:

    status_key = "tui.ledger.evidence.pending" if pending else "tui.ledger.evidence.reviewed"
    table.add_row(..., ledger_copy(status_key))

The call site passes a NAME, so the literal resolver saw no key there, and the
value is a bare scalar rather than a registry, so the constant and collection
rules had nothing to match either. Both branches were invisible -- and the
asymmetry is the same one S454 found in conditional kwargs: the branch that
ships is whichever the state selects, so the catalogue reads complete on the
path a developer happens to exercise.

The candidate value is deliberately narrow: a string constant, or a conditional
between them, and nothing else. A local bound to a dict, a call, or a subscript
is already the business of the registry and row-table rules, which confirm it
by how it is READ; widening this rule to any expression would let it claim
those shapes without that confirmation.

Shape alone still does not collect. A dotted literal in a local is as likely to
be a route or a lookup token as copy, so the name must reach a translator --
the same bargain every other shape here strikes.

I WROTE ONE GATE ASSERTION THAT WAS SIMPLY WRONG, and the correction is worth
keeping. It claimed a dict-bound local's key must not be collected at all;
running it showed the DICT rule collecting it, correctly, through the subscript
that reads the registry -- which is what that gate's own docstring says should
happen. The gate now asserts the boundary it meant: the local rule does not
CLAIM that name, while the registry rule still confirms the dict it owns.

Teeth: two defects, each restored by copy -- admit any expression as a
candidate value, and collect on shape alone. The first needed a stronger
fixture than the one I first wrote: with a subscript-bound local it did not
bite, because there is no literal inside `_ROUTES[token]` to over-collect. A
local bound to a CALL that mentions a module path is the form this campaign has
actually been bitten by, and against that fixture the defect bites.

## Notes

TARGET 2 REMAINS OPEN at 138 extras: 125 `cli.*`, 8 `tui.*`, 5 `application.*`.
Same two failures as before this step. No new breakage.

Residue: 5 full-literal, 35 tail-only, 98 no-trace. The full-literal remainder
includes two `frozenset` guards of safe display keys
(`_SAFE_PROVIDER_KEYS`, `_SAFE_SOURCE_KEYS`), whose values are validated
against rather than translated at the site that holds them.

OPERATOR DECISIONS UNCHANGED, all three now evidenced from live authorities:
the 125 `cli.*` (live command-spec registry declares none), the 5
`application.*` (live error registry declares none), and the `direction`
spelling, two of whose catalogue-side keys are among the 8 `tui.*`.

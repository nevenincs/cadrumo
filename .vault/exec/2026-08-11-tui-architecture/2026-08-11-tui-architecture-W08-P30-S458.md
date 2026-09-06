---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:701c1240996da3dd1cff4cb0c0f590b4bd5d3456a5d6f9dfe9066c4ab9a2b0b1'
step_id: 'S458'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Read the banner key a screen subclass declares as a class attribute and the base renders through the workspace copy helper, requiring the attribute name to reach a translator so a route or action id held the same way is still not mistaken for copy

## Scope

- `dev/locales/_ast_scanner.py`
- `dev/locales/tests/test_dynamic_prefix_registry_coverage.py`

## Changes

Parity extras: 182 -> 176. Full-literal residue 24 -> 18.

BLIND SPOT 9. A screen family names its own banner on the subclass and lets the
base render it:

    class AeatSyncCensusScreen(AeatSyncWorkspaceScreen):
        heading = "tui.aeat_sync.census.title"
    ...
        yield Static(aeat_sync_copy(self.heading), ...)

That declaration is not a call, not a suffix-named registry constant, and not a
collection, so every rule in the scanner looked straight past it and all six
subclass banners read as orphans.

Shape alone is again insufficient, and the counter-example is one this scanner
has already been bitten by: a class attribute holding a dotted literal is just
as likely to be a route or an action id as a key -- `workbench.home` is a
lookup token, not copy. The attribute NAME must be read into a translator
somewhere for its literals to count, which is the same bargain the dict and
row-table shapes already strike, and the sink set includes the boundary
wrappers from S453 because that is how every screen renders.

Teeth: two defects, each restored by copy -- collect on shape alone, and drop
the wrapper from the sink set. Each fails the gate, and the gate pins the
route-attribute negative beside the positive.

## Notes

TARGET 2 REMAINS OPEN at 176 extras. The suite run reports exactly the two
failures that preceded this step: the parity gate itself, and the shadow gate
on `tui.ledger.reconciliation.direction`. No new breakage.

The shadow failure is the BLOCKER recorded in S455 and sharpened in S457: the
code declares `direction` as a leaf and `direction.invoice_only` beneath it, so
the surface is self-inconsistent by the project's own rule. It is the other
writer's module and the rename has been reverted five times, so it waits on an
ownership decision rather than a sixth attempt.

Residue: 18 full-literal, 60 tail-only, 98 no-trace. What is left of the
full-literal group is a conditional `return` of one of two keys, a frozenset of
safe provider keys, and the AEAT Sync column tables -- which reach the
translator through a function PARAMETER and a second helper hop, interprocedural
in a way nothing closed so far has been.

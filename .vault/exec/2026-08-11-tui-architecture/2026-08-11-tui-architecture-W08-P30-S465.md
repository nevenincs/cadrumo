---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:18ad4f705e841a4bc131b966b4424acd286450fa1ec7eeed5987ebb26d8f1e74'
step_id: 'S465'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Read the display keys a boundary guard admits, linking the module that declares them to the screen that renders them through the membership test on a name the tree proves translatable, so an identically shaped allow-list of identities stays out

## Scope

- `dev/locales/_ast_scanner.py`
- `dev/locales/tests/test_dynamic_prefix_registry_coverage.py`

## Changes

Parity extras: 138 -> 136. Full-literal residue 5 -> 3, and two of the three
that remain are the blocked `direction_state` pair.

BLIND SPOT 13. A boundary that will not render an arbitrary string states the
keys it accepts:

    _SAFE_SOURCE_KEYS = frozenset({"tui.ledger.import.source.prepared"})
    if source_label_key not in _SAFE_SOURCE_KEYS:
        raise ...

and the screen beside it renders the admitted value as
`ledger_copy(choice.source_label_key)`. Nothing in the module that DECLARES the
keys translates them, and nothing in the module that translates them mentions a
literal, so each half looked inert on its own -- the security boundary that
makes this surface safe is exactly what made its keys invisible.

The link is the membership test, not a naming convention. The guarded name must
be one the tree actually passes to a translator, which is collected across all
modules because the proof and the declaration live in different files. An
identically shaped allow-list over a name nothing translates -- choice ids, in
the same module -- proves nothing about copy and stays out; the gate pins that
negative beside the positive.

THE WRAPPER BLINDNESS CAME BACK A THIRD TIME. Reading only `tr` found nothing
here at all, because every screen renders through its boundary helper. S453
taught the call-site resolver about wrappers and S455 taught flow confirmation;
this pass needed them too, and I wrote it without them first. The pattern is
now unmistakable: any new sink-side rule in this scanner must take the wrapper
set, because following the project's own boundary convention is what makes keys
invisible.

Teeth: two defects, each restored by copy -- drop the requirement that the
guarded name be translated, and drop the wrappers from the sink set. Each fails
the gate.

## Notes

TARGET 2 REMAINS OPEN at 136 extras: 125 `cli.*`, 6 `tui.*`, 5 `application.*`.
Same two failures as before this step. No new breakage.

THE SCANNER WORK ON THIS TARGET IS NOW ESSENTIALLY EXHAUSTED. Thirteen blind
spots have been closed across S453-S465, taking the extras from 463 to 136 and
the missing side from 228 to 2. Only three full-literal keys remain, two of them
the catalogue half of the blocked `direction` collision, and I have no further
live-call evidence to chase in the residue.

What is left is not scanner work but three decisions, each now evidenced from a
live authority rather than from absence:

* the 125 `cli.*` -- the live command-spec registry declares none of them, and
  the live command tree has no `config init` or `config get`;
* the 5 `application.*` -- the live error registry declares none of them, and
  that registry is in good standing in both directions;
* the `direction` spelling -- the code declares `direction` as a leaf AND
  `direction.invoice_only` beneath it, which the shadow gate rejects on the
  project's own rule.

The remaining 35 tail-only and 98 no-trace keys have no comparable authority to
consult, and "no literal found" has been wrong six times in this campaign. I am
not pruning them on absence of evidence.

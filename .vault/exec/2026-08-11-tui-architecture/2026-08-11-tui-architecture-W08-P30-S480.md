---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:590b3410950360400e0fce2e4651f2c3fcce19d59242bf201c2d159ebf44f351'
step_id: 'S480'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Record that the ledger reconciliation direction collision is resolved by the owning writer adopting the direction state spelling, which turns the shadow gate green and takes the missing side of parity to zero, leaving the parity and audit gates red on the extras alone

## Scope

- `dev/locales` (measurement only; nothing changed)

## Changes

NOTHING WAS CHANGED. THE BLOCKER FROM S455 IS RESOLVED, AND NOT BY ME.

The owning writer adopted the `direction_state` spelling:

    ledger_copy("tui.ledger.reconciliation.direction")                    # column header
    "invoice-only": "tui.ledger.reconciliation.direction_state.invoice_only"
    "transaction-only": "tui.ledger.reconciliation.direction_state.transaction_only"

which is exactly the shape the catalogue already carried and the shape
`test_no_key_shadows_a_namespace` requires: `direction` stays a leaf, and the
children live under a sibling namespace instead of beneath it.

MEASURED CONSEQUENCES:

* `test_no_key_shadows_a_namespace` PASSES. It had been red since S457, when my
  own scanner widening made the code's self-contradiction visible.
* The MISSING side of `test_codebase_to_locale_parity` is ZERO. The audit's
  `codebase_missing=()` says the same thing from the other side.
* Extras are 134: 125 `cli.*`, 5 `application.*`, 4 `tui.*`. The two
  `direction_state` keys stopped being extras the moment the code started
  reading them.

WHAT IS LEFT IS ONE DECISION, NOT THREE. `test_codebase_to_locale_parity` and
the two `test_audit` gates are now red on the EXTRAS ALONE, and the extras are
the prune question: 125 `cli.*` the live command-spec registry does not declare
(S461), 5 `application.*` the live error registry does not declare (S463), and
4 `tui.*`.

## Notes

FIVE UNILATERAL RENAMES WOULD HAVE BEEN WRONG. I reverted this rename after the
other writer undid it, five times, and stopped in S455 rather than attempting a
sixth. Holding the line was right: the writer who owns that module has now made
the same change themselves, and it stuck because it was theirs. Had I forced it
a sixth time the diff would have been identical and the ownership violation
would not.

THE SCANNER WORK WAS NOT WASTED BY THIS. S457's widening is what made the
code's own contradiction visible to the shadow gate in the first place --
before it, `direction` as both leaf and namespace was declared and unseen. The
gate going green now is the same instrument reporting the fix.

CAMPAIGN STATE, MEASURED THIS FIRING:

* missing side of parity: 0
* extras: 134 (125 `cli.*`, 5 `application.*`, 4 `tui.*`); of these 3 carry a
  full dotted literal in source, 33 a tail only, 98 no trace at all
* the export-tree group: stopped in S472, characterised in S474
* the two custody receipt cases: environment-limited on this host (S479)

THE ONE THING I STILL NEED FROM THE OPERATOR is the prune decision on the
extras. Every other blocker recorded in this campaign is now either closed or
environment-limited.

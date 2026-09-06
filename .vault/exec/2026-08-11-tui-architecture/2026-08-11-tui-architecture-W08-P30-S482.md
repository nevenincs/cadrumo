---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:bfc5ede3151a130070692631c408c70b31f6ce89526be67221d995633b8efa49'
step_id: 'S482'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Correct the claim that the four remaining tui extras have no authority to consult, since the workbench naming authority declares fourteen operator actions and neither of the two action keys is among them while their live siblings are, and the declarations and ledger surfaces render every sibling column and import state literally at the call site without the other two

## Scope

- `dev/locales` (measurement only; nothing changed)

## Changes

NOTHING WAS CHANGED. This step CORRECTS S481 and completes the evidence package
for the prune decision.

S481 SAID THE FOUR `tui.*` EXTRAS HAVE "NO COMPARABLE AUTHORITY". That was
wrong, and I only found out by looking for one instead of repeating the claim.

TWO ARE ANSWERED BY THE WORKBENCH'S OWN NAMING AUTHORITY. `search.py` declares
`workbench_action_label` "the single naming authority for an operator action
across the workbench: the palette and Home resolve the same identifier to the
same words". Its table declares 14 actions. Neither
`tui.aeat_sync.action.pull_comparison` nor `tui.home.action.label` is among
them -- while their live siblings `tui.aeat_sync.action.pull_filed` and
`pull_filed_all` are. An action key the single naming authority does not carry
is not an action this workbench can name.

THE OTHER TWO ARE ANSWERED BY THE SURFACES THAT RENDER THEM. The declarations
tables name every column at the call site --
`declarations_copy("tui.declarations.column.destination")`, `.availability`,
`.declaration`, `.when`, `.local_filing`, `.aeat_accepted` -- and
`column.calculation_revision` is not among them. The ledger import flow does the
same for `.title`, `.prompt`, `.confirm`, `.cancel`, `.confirming`, and does not
render `.empty`. These surfaces write their keys literally, so their silence is
enumerable rather than inferred.

## Notes

THE EVIDENCE PACKAGE IS NOW COMPLETE. Every one of the 132 extras has a verdict
from a live authority, and every verdict is the same -- not declared:

* 123 `cli.*` -- the live command-spec registry declares none of them, and the
  live command tree has no `config init` or `config get` (S461);
* 5 `application.*` -- the live error registry declares none of them, and that
  registry is in good standing in both directions (S463);
* 4 `tui.*` -- the workbench naming authority and the rendering surfaces above.

None of the 132 carries a dotted literal anywhere in source either (S481), and
fourteen scanner blind spots were closed reaching that state, each of which
turned keys that looked dead into keys plainly alive. That is why the absence
argument was never sufficient on its own and why the registries matter: they
answer the question the scanner cannot.

I STILL WILL NOT PRUNE. The decision to delete 132 shipped translations is the
operator's, and nothing above changes that -- it only means the operator now has
a per-group verdict from the authority that owns each namespace rather than my
accounting. Recommendation unchanged from S461: authorise the prune, gated by
the reverse-direction checks already in place
(`test_every_key_the_live_registry_declares_is_translated`), so a key the CLI
actually resolves can never be removed by it.

STILL OPEN: the export-tree group stopped in S472 and characterised in S474, and
the two custody receipt cases environment-limited on this host (S479).

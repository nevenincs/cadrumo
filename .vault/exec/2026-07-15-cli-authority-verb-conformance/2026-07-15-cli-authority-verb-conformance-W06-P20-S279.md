---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S279'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Refer the config CLI module size breach to the peer TUI campaign that caused it, since the module stood at 1254 lines inside budget before the manager-from-create commit added 134

## Scope

- `src/cadrumo/entrypoints/cli/_config/__init__.py`

## Description

- Re-run the size budget gate at HEAD rather than inheriting the reported
  breach.
- Reconstruct each over-budget module's line count at every recent commit
  touching it, and identify the commit that crossed the ceiling.
- Refer each breach to the campaign that actually caused it.

## Outcome

SATISFIED as a referral, with the Step's own premise corrected. Neither
current breach belongs to this campaign, and neither is the breach the Step
was written about.

The gate is red at HEAD with two modules over a 1250-line ceiling, and the
Step's named subject is not one of them in the way it describes. Line counts
reconstructed per commit, which is the only thing that settles attribution:

The config CLI facade was at 1390 lines under a peer interface commit, and
this campaign's own retirement commit reduced it to 1385 - a contribution of
minus five. A peer then extracted the wizard manager dispatch and took it to
1205, comfortably inside budget. So the breach this Step exists to refer was
already remediated by its owner, two days before this verification. The
module is over again today at 1252, but by a different commit from a
different peer refactor that added 47 lines while splitting complexity
hotspots. Referring that to the interface campaign named in the Step would
have been referring a resolved breach to the wrong owner.

A second module is over that no prior record mentions: the Clave Movil auth
adapter at 1268. Its trajectory is 1060, then 1141, then 1214 - under budget
throughout - crossing to 1268 today in a commit salvaging an authenticated
session after a post-auth failure. That is the AEAT auth adapter surface,
untouched by this campaign.

Both breaches are therefore referred to their owning campaigns, and the
campaign-close position is unchanged and now re-established rather than
assumed: no feature-owned size regression exists.

Gates at HEAD `4cb601d10dc9921c833c77c79dcf9f5302ebb84a`:

- `uv run --no-sync pytest src/cadrumo/tests/test_codebase_size_budgets.py
  -m "" -n0` collected 16 cases and exited `1 failed, 15 passed in 26.96s`.
  The single failure enumerates both modules above; it is peer-owned in full.

## Notes

The instructive part is that this Step would have produced a wrong action if
executed on its own text. It names a cause, an owner and a remedy, all of
which were accurate when written and none of which survived three days. The
module it names is over budget, which is exactly the coincidence that makes
the stale premise hard to see: a reader confirming "is the config module over
budget?" gets yes, and stops.

What distinguishes the two is the trajectory, not the current value. The same
reconstruction that showed the original breach resolved also showed a second
module breaching unremarked, which no amount of re-reading the Step would
have surfaced.

The ceiling itself moved too - the prior record quotes 1261 where the gate now
enforces 1250 - so a comparison against the old figure would have mis-stated
the margin in both directions.

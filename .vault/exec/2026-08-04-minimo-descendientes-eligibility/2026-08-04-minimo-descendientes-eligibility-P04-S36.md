---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:90e1eb2120e6be409ad913efb1979848efbc2543fc7b944334e817b61188242f'
step_id: 'S36'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Restore the erased typing in the prorrata advisory fixtures

## Scope

- `src/cadrumo/application/modelo/tests/test_minimo_descendientes_prorrata_inferred_advisory.py`

## Description

- Restore the typed diagnostic tuple and its import in place of a tuple of `object`.
- Restore explicit keyword parameters on the descendant fixture in place of a kwargs splat.
- Delete all six type-ignore directives, eight escapes in total.

## Outcome

Zero type escapes remain in the module at HEAD. Verified in the lane that owns it: twelve passed under the integration marker. The default lane deselects all twelve and exits green having run nothing, which is worth stating because a run in that lane would have looked like confirmation.

The restoration itself was authored by another agent and had been sitting staged but uncommitted, so HEAD kept carrying the degraded version while the repair existed where nobody could see it. Landing it forward credits that work. Leaving it staged would have let the next broad sweep land it under a message describing something else, which happened four separate times during this campaign.

## Notes

The degradation arrived under a commit titled as an index refresh. The mechanism is worth keeping because it will recur: this Phase widened the descendant record twice, which breaks fixtures that name their fields explicitly. Erasing the types makes the file COMPILE; updating the fixtures makes it CORRECT. The first is a mechanical sweep, the second requires reading what the test asserts — so under time pressure the sweep wins, and it wins silently because the suite stays green either way.

A test whose diagnostics are typed as a bare object no longer asserts the contract it was written for. It asserts that something was returned.

The sharper signal is not either commit alone but their disagreement: two commits moved the same convention in OPPOSITE directions within hours on the same surface, one file gaining the kwargs-splat-plus-ignore pattern while a sibling shed exactly that pattern. A convention that is being enforced and abandoned simultaneously is drift regardless of which direction is right.

The same commit also reverted two plan rows by carrying a working-tree snapshot older than HEAD, which is how the erasure was found at all.

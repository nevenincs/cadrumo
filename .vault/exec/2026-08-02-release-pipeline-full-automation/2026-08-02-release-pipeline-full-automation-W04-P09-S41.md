---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:3ae4aa7d7681119782b166b7c2155e6fe7f941da841a6c1e1278158af015ecd3'
step_id: 'S41'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---
# Make the promoter selection skip past a non-promotable candidate rather than returning on the first one, and retire a rehearsal candidate out of the selectable namespace once its window closes

## Scope

- `dev/release/soak_promoter.py`
- `dev/release/tests/test_soak_promoter.py`

## Description

- Add `elapsed_candidates`, returning every candidate whose window has closed, eldest first.
- Rewrite `promote_once` to ITERATE that list rather than stopping on the first entry.
- Retire a completed rehearsal candidate through the consume action and continue the loop.
- Keep an invalidated candidate STOPPING the tick, deliberately, and mark the decision `invalidated` for S44's exit status.
- Add two regression tests, the first deliberately multi-candidate with the rehearsal eldest.

## Outcome

`uv run --no-sync pytest dev/release/tests/test_soak_promoter.py -q` reports 20 passed. Lint, format, and `ty check` clean.

Verified the way the auditor verified the bug, by execution rather than by reading: replaying their three-tick probe over a rehearsal plus a real candidate now dispatches the real candidate on tick 1, exactly once, and leaves the forge empty. Before the fix the same probe dispatched nothing on all three ticks.

## Notes

The audit is right, and the diagnosis is worth restating because the shape recurs. A rehearsal seals a REAL draft in the deliberately garbage-collector-exempt namespace. That exemption is correct for a real candidate and permanent for a rehearsal one, so refusing a rehearsal WITHOUT retiring it left it selectable forever, and because `promote_once` returned on the first selected candidate, every real candidate sealed afterwards sat behind it. The tick still returned a decided result, so the exit status stayed zero and the failure-guarded alert never fired. Publishing-never, silently, reachable from the default value of the first input an operator ever supplies.

Two candidates are now treated differently on purpose. A rehearsal is retired and the loop CONTINUES, because it is not a release and nobody needs to act on it. An invalidated candidate STOPS the tick, because it is a real release whose cohort regressed and it needs a human; S44 gives that verdict a non-zero exit so the alert fires. Skipping past an invalidated candidate would have been the tidier-looking loop and would have buried a real regression under the next promotion.

The fixture in the new regression is multi-candidate with the rehearsal deliberately ELDEST, so it is selected first and genuinely blocks. The audit names the single-element fixture in my original rehearsal test as what let this ship green, and that is exactly right: a one-candidate fixture cannot express "starves the one behind it", so the test asserted the refusal and was blind to its consequence. The original test is kept - it still pins that a rehearsal never publishes - and the new ones cover the interaction it structurally could not see.

## Blocked / not done here

`dev/release/environment_inventory.py` carries uncommitted peer WIP (the `release-alert` label probe for the sibling finding). Confirmed by `git status` before staging and deliberately excluded from this commit's pathspec.

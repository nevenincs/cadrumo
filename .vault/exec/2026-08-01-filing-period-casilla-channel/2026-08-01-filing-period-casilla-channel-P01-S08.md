---
tags:
  - '#exec'
  - '#filing-period-casilla-channel'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:5a58db714e3b130a48938110457380b8b1598232ec3d0d8339535ad9064c7f4f'
step_id: 'S08'
related:
  - "[[2026-08-01-filing-period-casilla-channel-plan]]"
---

# Add the anti-tautology proof that an ordinal-shaped persisted period value is refused loudly at draft build

## Scope

- `src/cadrumo/application/filing/tests/test_text_casilla_routing.py`

## Description

- Add a build-gate test asserting an ordinal-shaped period value is refused when a stale revision replays it into the draft builder.
- Prove the coverage is not tautological by reverting the fix and measuring the result.
- Prove the paired fix direction the same way, by reverting the token fill.
- Restore both mutations and re-measure green.

## Outcome

The proof targets the BUILD GATE and claims nothing beyond it. This is stated in the test's own docstring, not only here. A strict validating load of the persisted revision cannot refuse the stale value, because the string replay mapping is typed as string-to-string and an ordinal-shaped value is a perfectly well-formed string that is merely the wrong one. The refusal comes from the period-code validator at draft build. No load-time proof was written and none is claimed anywhere in the commit.

First mutation, restoring the retired literal membership filter so the casilla routes back to the Decimal channel. The new test reported one failure in 11.63 seconds, with the assertion recorded as a regex pattern that did not match - the build succeeded where the test demands a refusal.

Second mutation, restoring the ordinal fill. Eight failed and seven passed in 32.85 seconds: the four parametrised quarterly cases, the provenance test, both parametrised token cases in the semantic-role resolver test, and the extended-quarter case.

Both mutations flip an assertion rather than merely killing a fixture. The first makes the builder accept a value the test requires it to reject; the second puts the ordinal back on the channel the test requires to hold zero.

Both were restored immediately. Restoration was verified by diffstat identity rather than by assumption - the adopted module returned to 34 changed lines and the authored module to 27 insertions and 13 deletions, each matching its pre-mutation value - and the five affected test modules then reported 25 passed in 51.07 seconds.

## Notes

Each mutation window was held to a single targeted single-process test run, because this worktree is shared and a deliberately broken tree can give a peer a false red. Neither window exceeded a minute of wall time.

The adopted routing set carries its own paired refusal test for a malformed extended period code. The test added here is the stale-ordinal case specifically, which is the shape a pre-fix revision actually produces on replay.

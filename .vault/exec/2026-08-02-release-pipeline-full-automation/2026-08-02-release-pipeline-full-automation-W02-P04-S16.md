---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:1c8f35c174d64f0a78ded3c560f1fab7d2dd6122e65de7296104acfe35f9a720'
step_id: 'S16'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---
# Build the promoter selection logic that lists sealed candidates, selects the eldest whose soak deadline has elapsed against a real clock, and refuses every candidate whose window is still open, because publishing early is the one failure this mechanism exists to prevent and a wrong comparison publishes early silently, gate: uv run --no-sync pytest dev/release/tests/test_soak_promoter.py -q passes covering an elapsed candidate selected, a not-yet-elapsed candidate refused, a boundary candidate at exactly the minimum window, and an empty candidate set returning no promotion rather than an error

## Scope

- `dev/release/soak_promoter.py`
- `dev/release/tests/test_soak_promoter.py`

## Description

- Add `select_promotable`, pure over already-loaded candidates plus an explicit `now`, returning a `PromotionDecision` that always carries an operator-facing reason.
- Select the eldest elapsed candidate by soak deadline, tie-broken by packaging run id.
- Refuse an open window with a reason naming the remaining time and the deadline instant.
- Return a non-promoting decision rather than raising when no candidate exists.
- Add six tests covering selection, refusal, both boundary neighbours, the empty set, eldest-first ordering, and a mixed set.

## Outcome

`uv run --no-sync pytest dev/release/tests/test_soak_promoter.py -q` reports 6 passed. Lint, format, and `ty check` are clean.

## Notes

The asymmetry between the two failure directions drove the whole design and is stated in the module docstring so the next editor inherits it. Publishing LATE is self-reporting: the candidate sits, the release does not appear, someone asks. Publishing EARLY is silent - the release happens, looks entirely ordinary, and the soak simply did not occur, with no artifact recording that the window was short. Every comparison is therefore tested on both sides and exactly at the edge, rather than only on the happy path.

The boundary is inclusive, and both neighbours are asserted rather than just the boundary itself. An exclusive comparison would make every window imperceptibly longer than the declared policy - harmless but wrong - while comparing against `opened_at` rather than the deadline would publish immediately. Neither shows up in any output; only a test distinguishes them.

Eldest-first is a correctness property, not a preference. Promoting the newer of two elapsed candidates first would burn a version above the older one, and the unchanged version-identity authority would then refuse the older candidate permanently - a permanent stall produced entirely by selection order, and one that would look like a mysteriously stuck release rather than an ordering bug.

A tick that promotes nothing returns a decision rather than raising, because most ticks land inside some candidate's window; making the ordinary case an exception would train whoever reads the alerting channel to ignore it. The refusal still distinguishes "no candidates at all" from "something is waiting and here is how long", since those are indistinguishable in a log that only reports promotions.

The mixed-set test carries an explicit control asserting the second candidate really is still soaking at that instant, so the selection result cannot be read as a coincidence of the fixture.

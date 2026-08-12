---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:4c506ac89201ee45fdc2b0055422e1ff779a21c39ab2cd2173493cf6309dd3b2'
step_id: 'S35'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Decide what surfaces a lane-reachability regression within minutes rather than hours, because the gate went red at 07:21 and nobody noticed for five hours despite it living where nine lanes reach it and failing in twenty-eight seconds, and because the enrolment that closed today's instance fixes one directory rather than the arrival rate, so the next test directory created outside every lane path scope repeats it exactly, and today's zero-failure result is a property of one campaign happening to write correct tests rather than a property of the void which discards whatever arrives in it, noting the remedy cannot be a scheduled run because that is refused by standing operator ruling and cannot be a hardcoded directory list because a list encodes today and detects nothing tomorrow

## Scope

- `src/cadrumo/tests/test_lane_reachability.py and the lane declarations it reads`

## Description

- Ask why the five-hour gap existed before proposing anything to close it,
  because a latency defect and a missing-instrument defect need opposite
  remedies.
- Establish whether the gate is selected by the per-push blocking lane, rather
  than assuming from its location that it is.
- Check whether the mechanism that produced the gap is still live.
- Record the decision.

## Outcome

DECISION: nothing new is built. The minutes-scale signal already exists, it
already reaches this gate, and the defect that hid it for five hours has
already been repaired by a separate landing.

The gate carries `pytest.mark.unit` and lives under `src/cadrumo/tests`, which
is inside `testpaths`. The `test-unit` recipe passes no paths and therefore
inherits testpaths, and ci.yml invokes `just test-unit` in the per-push unit
job with no continue-on-error. So a push already runs this gate, blocking, and
the gate fails in 28 seconds. Every ingredient for a minutes-scale signal was
present on the day of the incident.

What was missing was a run that could FINISH. The per-push lane carried an
unconditional `cancel-in-progress: true` on a push trigger, so each push
cancelled the run the previous push started, and at this fleet's commit rate --
roughly 19 commits per 12-minute window -- essentially no run ever completed.
The lane measured 99 cancelled of its last 100. A gate that reds in 28 seconds
inside a job that is killed at 3 minutes is indistinguishable from a gate
nobody reaches, and reports identically as absence from a FAILED list. That is
the same reporting collapse S45 states as this campaign's durable finding.

That mechanism is now repaired: ci.yml reads
`cancel-in-progress: ${{ github.event_name == 'pull_request' }}`, so pushes
queue and only pull requests supersede. The row's question therefore has an
answer that requires no construction, and proposing an instrument here would
have added a second signal for a question the first already answers -- while
the first was merely unable to report.

This also satisfies both constraints the row names without straining. It is not
a scheduled run, which standing operator ruling refuses. It is not a hardcoded
directory list, because the gate asks the property directly -- whether some
lane selects each test -- so a directory created tomorrow outside every lane
scope reds it exactly as one created today would. The arrival-rate half of the
row was never the unsolved half. Only the latency was, and latency was a
cancellation defect wearing a coverage defect's clothes.

## Notes

CARRY-FORWARD, and this row does not close it: the decision above is sound on
the configuration but has NOT been confirmed against an observed completed
per-push run. That confirmation is the same evidence class S01, S03 and S10
wait on, and it is unavailable from here -- a 142-file unresolved merge is open
in this worktree, so nothing can be pushed and the collection this gate needs
does not even parse at present. The honest statement is that the mechanism is
repaired and the wiring is verified by reading, and that one green per-push run
converts that into observation. Whoever observes it should note it against this
row rather than re-deciding it.

The near-miss recorded for the next reader: the attractive remedy here was a
new watcher of some kind, and it would have been the sixth remedy in this row
family to be wider than the defect it targets, after a CPU bound that cannot
fire on a wedge, a report hook that cannot fire on Windows, a raw descriptor
write the exit discards, a reachability change dominated by what it never meant
to reach, and a wall advisory printed where capture would discard it. The
question that stopped it was the one this campaign keeps having to re-learn:
before building an instrument, ask on which failure and on which platform the
EXISTING one actually executes. Here it executed correctly and was killed
mid-sentence.

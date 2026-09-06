---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:70dbb0a2874c9bb34608520d15992c8232d0bde415721bbdf507c7855584664f'
step_id: 'S67'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---
# Stop the queue watchdog from cancelling a run on a single sample of a label-set handoff

## Scope

- `dev/ci/runner_queue_watchdog.py`

## Changes

- `M` `dev/ci/runner_queue_watchdog.py`
- `M` `dev/ci/tests/test_runner_queue_watchdog.py`
- `verify:` `pytest dev/ci/tests/test_runner_queue_watchdog.py -n0 -m ''` -> `pass`
- `verify:` `ruff check dev/ci/` -> `pass`
- `verify:` `python -m dev.quality.types` -> `pass`

## Notes

Run 34016654501 was cancelled by its own canary on a race, not on a starved
lane. The Windows wheel job occupied `[Windows, X64, self-hosted]` for 67
minutes; it completed at 08:24:03, the Windows oracle that had been queued
behind it started at 08:24:04, and the watchdog polled at 08:24:06. That single
sample saw a job queued 3992s and nothing running on its labels, which is
indistinguishable from a lane no runner serves, so it cancelled the run and the
six lanes still in it, including the three that mint the acquisition-evidence
rows.

The occupancy discriminator was sound; what was missing is that occupancy is
sampled, and one empty sample is not proof. A handoff gap closes on the next
poll and a genuinely unservable lane never does, so the verdict must now hold
across consecutive polls before the run is cancelled. Two, by default. The
cancel is destructive and unrecoverable, so it is the side that pays the extra
poll interval against a 300s threshold.

The tally is rebuilt from each poll rather than decremented, so two unrelated
handoff gaps minutes apart cannot add up to a cancellation neither justified.

The debounce is a pure function so it is exercised without stubbing the HTTP
boundary, matching the module's existing shape. Three cases cover it: the
single-sample shape that killed the run stays silent, a verdict holding across
consecutive polls still cancels, and a recovered lane restarts its count. The
silent case additionally asserts that the same input under the pre-fix
threshold does confirm, so it cannot pass against a function that confirms
nothing.

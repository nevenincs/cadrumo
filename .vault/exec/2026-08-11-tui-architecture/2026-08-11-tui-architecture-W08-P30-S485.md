---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:08f8588bd5c83d336c9dd40d0567fcc590aae5b132d282bfef910598cbf1d395'
step_id: 'S485'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Correct the attribution for the packaging build timeouts, since running the scoop suite with nothing of mine in flight still finds the host saturated with more python processes than before, so the contention is not this sessions and the gates exceed their configured timeout on this machine as it is actually shared

## Scope

- `packaging/` (measurement only; nothing changed)

## Changes

NOTHING WAS CHANGED. This corrects an attribution I made in S484 on no evidence.

S484 SAID "I AM PART OF WHAT MADE THIS LOOK RED", reasoning that the 110 python
processes in the host-load line were largely this session's background suites.
That was a guess dressed as a finding. Tested it: ran the scoop suite at the
project's default `timeout = 300` with nothing of mine in flight.

    before, with my suites running:  processes=1071  python_processes=110
    after, with nothing of mine:     processes=1130  python_processes=150

MORE load, not less. The contention is not this session's, and the suite still
times out at the configured limit. What S484 recorded as my own interference is
the machine's steady state while another writer works it.

WHAT THAT CHANGES AND WHAT IT DOES NOT. The gates are still SOUND -- given 1200s
both suites pass (5 scoop in 501s, 3 homebrew in 351s, S484). What changes is
the reading: on this machine as it is actually shared, these packaging builds
exceed their 300s budget, and no quiet moment I can arrange fixes that. It is
not a defect I introduced and not one I can measure away.

## Notes

THE ERROR IS THE SAME SHAPE AS THE ONES THIS CAMPAIGN KEEPS FINDING, which is
why it is worth a record rather than a quiet edit. I inferred a cause from a
plausible story -- "I have been running heavy suites, so the load is mine" --
exactly as I inferred "the records are unchanged" from a gate's silence in S472,
and "the tui extras have no authority" in S481. In all three the correction came
from measuring the thing itself rather than reasoning about it.

FOR WHOEVER OWNS THE PACKAGING GATES: the useful facts are that the builds take
351s and 501s against a 300s budget under normal shared-machine load, that they
instrument their own host load already, and that the timeout is configured
repository-wide in `pyproject.toml` rather than per-suite. Whether that budget
should rise for these two, or the builds should get cheaper, is a decision for
their owner; I have not touched either.

UNCHANGED AND STILL THE ONLY OUTSTANDING WORK:

* THE PRUNE -- 132 catalogue extras, each not-declared by the live authority
  owning its namespace (S461, S463, S482), none written down anywhere (S481).
* THE EXPORT TREES -- 27 serializer-only rewrites on an active writer's surface,
  plus `m390-2022` needing an operator's `_CHECK_MODE_PENDING` reason (S472,
  S474).
* THE TWO CUSTODY CASES -- environment-limited on this host (S479).

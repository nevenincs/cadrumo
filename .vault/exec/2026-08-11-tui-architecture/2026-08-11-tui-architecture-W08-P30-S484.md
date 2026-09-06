---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:a90c29c4fa7952f0c346178e9f8a79a2a0ac09bba2e0f5c562779aa715f0306b'
step_id: 'S484'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Sweep the packaging test root that neither earlier sweep reached and establish that both its suites pass, the scoop and homebrew builds simply exceeding the configured three hundred second timeout under host contention rather than failing

## Scope

- `packaging/` (measurement only; nothing changed)

## Changes

NOTHING WAS CHANGED. The last surface neither sweep reached is measured, and it
is green.

S483 CLOSED WITH A CLAIM I HAD NOT TESTED: "if more gates exist, they are on
surfaces neither the `dev/` nor the `src/` sweep reached". That is checkable, and
S482 had just taught me what happens when I repeat a claim instead of looking --
so I looked. Two test roots existed outside both sweeps:

    packaging/homebrew/tests/test_homebrew_generate.py
    packaging/scoop/tests/test_scoop_generate.py

BOTH PASS. 5 scoop tests in 501s, 3 homebrew tests in 351s.

THEY LOOKED LIKE FAILURES AT FIRST AND WERE NOT. Run under the project's own
configuration they hit `+++ Timeout +++` and the run exited non-zero, which is
exactly what a broken gate looks like from the summary line. The configured
`timeout = 300` in `pyproject.toml` is what they exceeded; given 1200s both
suites complete cleanly.

THE TEST SAID SO ITSELF, in output I nearly skipped past:

    working tree carries 8 uncommitted path(s); building from a pristine HEAD
    extract so the artifacts correspond to a commit
    CADRUMO-HOST-LOAD ... cpu=100.0% cpus=24 mem=85.6% processes=1071
    python_processes=110 lead=2.0s

These suites build a real artifact from a pristine HEAD extract. The project
instruments them with a host-load line precisely because the build's wall time
depends on the machine, and 110 concurrent python processes is a machine under
load -- much of it my own background runs, alongside the other writer's.

## Notes

I AM PART OF WHAT MADE THIS LOOK RED. The load line names 110 python processes;
this session has been running long background suites throughout. A timeout I
provoked is not a finding about the repository, and reporting it as one would
have been the same error as reading a parallel run's failure list as the failing
set (S473).

THIS IS A THIRD ENVIRONMENT CLASS, distinct from the two already recorded. S479
was a missing dependency (no reachable credential store). S473 was parallel-run
unreliability. This is wall-time under contention: the gate is sound, the host
is busy, and the only honest reading needs the timeout raised or the machine
quiet.

WHERE THE CAMPAIGN STANDS. Every test root in this repository has now been
measured -- `dev/`, `dev/locales`, `src/cadrumo`, and `packaging/` -- and the
only outstanding items are the three already recorded:

* THE PRUNE -- 132 catalogue extras, each not-declared by the live authority
  owning its namespace (S461, S463, S482), none written down anywhere (S481).
* THE EXPORT TREES -- 27 serializer-only rewrites on an active writer's surface,
  plus `m390-2022` needing an operator's `_CHECK_MODE_PENDING` reason (S472,
  S474).
* THE TWO CUSTODY CASES -- environment-limited on this host (S479).

I no longer have an untested claim about where more work might be.

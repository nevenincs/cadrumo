---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S273'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Make a stale import-linter ignore fail loudly and distinctly from a contract breach, so an aborted run cannot read as a quiet one

## Scope

- `.importlinter`

## Description

- Establish which half of the loud-failure requirement was already met and
  which was not.
- Give the layering dimension a declared-versus-evaluated floor so an aborted
  run reports as a rotted configuration rather than as a breach.
- Replace the tautological gate over that dimension with a real-behaviour one
  that reproduces a stale ignore.

## Outcome

SATISFIED, and the missing half was not where the row points.

The tool-level half was already in place: every contract in `.importlinter`
declares `unmatched_ignore_imports_alerting = error`, so import-linter itself
refuses an ignore entry matching nothing. Confirmed by reproducing it - a
stale entry produces `No matches for ignored import ...` and exit 1, with NO
contract results printed at all.

The missing half is in the layer that READS that result, which is why the row's
scope line points at the config and the fix lands next to it. The health
report classified an aborted run as `0 import-linter contract(s) broken` -
technically true and completely misleading, because zero contracts were broken
for the same reason zero were kept: none was evaluated. A reader chasing that
headline hunts for a layering violation that was never reported. Worse, the
GREEN branch carried no floor at all: it reported `all {kept} contract(s)
kept`, which reads identically whether that count is five or zero.

The dimension now compares EVALUATED against DECLARED, reading the declared
count from the config itself. An aborted run is RED with a headline naming
`evaluated 0 of 5 declared contract(s); the run aborted rather than reporting
a breach`, and a detail telling the reader to fix the ignore list rather than
hunt a violation. A genuine breach keeps its own headline, now qualified with
how many contracts were evaluated. A third branch catches the remaining
contradiction - a non-zero exit while every contract reports kept.

The gate over this dimension was itself the tautology this campaign exists to
remove. It asserted `status in {RED, AMBER, GREEN}` - the entire enum, true
whatever the dimension says - and would have passed unchanged throughout the
period the contracts were not being evaluated. The sibling duplication test
directly below it records the same defect against its OWN earlier form, so the
pattern was already known in this very module and had not been swept.

Its replacement is real-behaviour with no mocking: it copies the live config,
injects an ignore naming a module that does not exist, and runs the real
import-linter against it, then asserts the aborted classification is distinct
from a breach. A second test asserts the floor on the live tree.

MUTATION-PROVEN rather than asserted. Disabling the declared-count floor
changes the aborted headline from `...the run aborted rather than reporting a
breach` to `...the signal is self-contradictory`, so the assertion requiring
the word `aborted` goes from true to false and the test reds. Also recorded:
even with the floor disabled the third branch still refuses to call it green,
so the two guards are defence in depth rather than one guard with a spare.

Availability is asserted rather than tolerated. Both tests would have passed
vacuously on a machine without the executable, via the sanctioned
signal-unavailable AMBER - the identical shape they exist to catch. They now
assert the executable resolves and fail loudly if it does not.

Gates at HEAD `19ab62dc0ef77c6aaa16b3d0c0388dbce3bb9061`:

- `uv run --no-sync pytest src/cadrumo/tests/test_dev_audit_report.py -n0
  -k layering` collected 2 cases and exited `2 passed in 2.66s`.
- The live dimension reports `all 5 of 5 import-linter contract(s) kept`, so
  every declared contract is evaluated and kept at this HEAD.
- `ruff check` and `ruff format --check` clean on both touched files.

## Notes

The two broken layered contracts the close review found are no longer broken.
It measured three kept and two broken; the live run at this HEAD evaluates all
five and keeps all five. Their owning campaigns resolved them in the interim,
which is the outcome the sibling row asked for rather than something done here.

The 2.66-second runtime was checked rather than trusted, because it looked far
too fast for two real import-linter invocations. It is genuine: the executable
resolves and a full run over the live graph completes in about 0.9 seconds
against a warm cache, and the aborted run refuses before building the graph at
all. A fast green is exactly what a vacuous test looks like, so the timing was
worth one command to settle.

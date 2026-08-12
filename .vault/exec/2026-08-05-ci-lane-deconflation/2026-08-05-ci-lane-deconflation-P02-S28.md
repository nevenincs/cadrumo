---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:f8116e78b2549265d66027b3b50fcfba592efc7a52a14252b954a59a8546a09b'
step_id: 'S28'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Convert the two wall-clock budgets guarding the integration serial step so that a process CPU-time bound becomes the failure condition while the wall-clock threshold is retained as a loud advisory, because the budgets were measured on a box shared with the dev machine and the agent fleet and flake under load regardless of code quality, and because a straight conversion would delete the only bound that catches a genuine share hang given that a test blocked on I/O burns almost no CPU, applying the repository control-plane invariant that perf gates assert process CPU-time with wall advisory only rather than inventing a remedy, noting the perf marker is not available as an escape because it is absent from _CI_INCAPABLE_MARKERS and the perf lane is path-scoped to dev/packaging, and covering the two named budgets only while inheriting the load stamp owned by the pytest ceiling row

## Scope

- `the two integration serial budget tests and .github/workflows/ci-full.yml`

## Description

- Measure both named budgets at HEAD before changing anything, and find the
  CPU half of this row already landed: the quarterly IVA P95 asserts process
  CPU-time against a 3.0 CPU-s ceiling with a non-vacuity control, and the
  cold start asserts marginal child CPU-time against the same figure. Neither
  needed converting.
- Find the half this row names that had NOT landed. Both sites kept a wall
  figure and both emitted it with `print`, and the broad serial pass runs
  `pytest -q ... -n0` with no `-s`, so fd-level capture discards prints from a
  test that passes. Both call sites described the wall figure as "never
  asserted", which was accurate and understated: it was also never readable.
- Add `wall_advisory_message` to the perf-measurement module that already
  declares itself the single home for this fleet's load-immune measurement,
  emitting on the warnings channel rather than stdout.
- Gate the emission on wall crossing its retained threshold AND the
  wall-to-CPU ratio being wedge-shaped, with the ratio supplied per site.
- Wire both budgets to it and correct the two module docstrings that recorded
  the print as the advisory mechanism.
- Add the gate proving the advisory fires on a wedge, on a fully-blocked
  zero-CPU sample, and on a stalled spawn, and proving it stays silent on the
  worst load either site ever measured.

## Outcome

Landed as `19ec4dcac6840f6c33bd65d91045f315ab0478cf` (83/1 perf measurement,
172/0 new gate, 37/1 ledger benchmark, 31/2 cold start).

The row's stated remedy is complete, but its two halves closed very
differently and the record is worth keeping straight. The CPU conversion this
row was written to perform was already in the tree. What was actually open was
the clause the row added almost as a caveat -- that a straight conversion
deletes the only bound catching a share hang -- and that clause turned out to
describe the live state exactly: a test blocked on a stalled mount burns no
CPU, so the CPU ceilings are blind to it by construction, and the wall figure
retained beside them could not be read on any passing CI run.

The reachability defect is the substantive find. The repository already knew
the `-s` mechanism was load-bearing and had pinned it for the perf lane in the
perf-gate policy gate. These two budgets are not perf-marked -- deliberately,
since the row records that the perf marker would make them CI-unreachable --
so they fell outside that pin and nothing replaced it for them. The advisory
existed, was correct, and was structurally unreadable in the only lane that
runs it. That is the same shape as this campaign's repeated finding: an
instrument present for the adjacent question and absent for this one.

The ratio condition is what keeps the retained bound from decaying. A bare
wall threshold on this box is crossed on ordinary days -- the quarterly path's
own recorded loaded reading is 4.10 s against a 3.0 s threshold -- and an
advisory that fires on ordinary days is one every reader learns to skip, which
is the decorative-guard decay already documented twice in this plan. Load
inflates both clocks; a block inflates only wall. So both conditions are
required, and the message states which shape it saw.

The ratio is per-site rather than global, and that was measured rather than
assumed. The in-process aggregation ran 1.13x quiet and 2.24x under full fleet
load. A subprocess cold start pays process-creation wait the code under test
does not answer for -- a bare `python -c "import sys"` measured 1.63-5.00 s of
wall for 0.08 s of CPU on this box -- and the measured CLI spawn reached 4.7x
while healthy. One global figure would have to be noisy at the first site or
blind at the second, so each carries its own derived from its own maximum.

Proved in both failure directions by runtime mutation from outside the
repository, with no tracked file altered. An advisory that never warns reds
three assertions; one that ignores the ratio and fires on any threshold
crossing reds the measured-loaded-reading control. The real implementation
passes all seven.

## Notes

This row does NOT close S10, and the distinction matters because S10's
verification criterion is explicitly an observed runner execution. What S28
removes is the objection that a green serial step might be green only because
the box was quiet. That objection is now answered for the two named budgets:
the failure condition is CPU-time, which the fleet measured as varying 1.4x
against wall's 20x. The remaining S10 precondition -- watching the serial
pass complete once on a runner, including its build branch producing three
wheels and three sdists -- is untouched by this row and stays open.

The wall advisory is deliberately NOT wired to the host-load stamp that S29
landed. That stamp is reached from a pre-timeout timer and writes through the
terminal writer because it must survive `os._exit`; this advisory runs inside
a passing test where the warnings channel is available and sufficient. Reusing
the stamp would also mean a cross-package private import, which the
architecture boundary forbids. The two instruments answer different questions
at different moments and are correctly separate.

Six unrelated gates are red in `dev/ci/tests` and `dev/quality/tests` at the
time of this record and none are caused by this row: an unwatched off-lane job
in `ci-runner-probe.yml`, nineteen packaging workflows using Actions artifact
storage, operator-identifying tokens in committed vault text, an exec-outcome
baseline overrun of 2166 against 1879, and a workflow-conformance gate still
pinning a `--ignore` directive that this plan's own S31 removed. The last of
those is this campaign's surface and is rowed separately rather than absorbed
here, because it belongs to S31's close rather than to this one.

---
tags:
  - '#reference'
  - '#test-harness-sanity'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:b0dc99479686c62b7bd6dec78f60028be4a212fbbb438c5c43fe7e090d9616f5'
related:
  - "[[2026-08-14-test-harness-sanity-harness-performance-audit]]"
---
## Why this exists

The performance campaign recorded in
the harness-performance audit (see `related:`) reached the point
where every identified cost is taken, structural, or under ~1.6% of suite CPU.
What is expensive now is REDISCOVERING that: each confirming profile costs about
half an hour of a machine several agents share.

This is the baseline so a later round can run one profile and DIFF, instead of
re-deriving the same conclusions. It is a measurement record, not a target list.

## The shape, as measured

Full `src/cadrumo` run, 6 workers, `--dist=loadfile`, quiet box:

    recorded CPU        : 9,351s across 2,326 files
    suite wall clock    : ~1,840-1,920s
    perfect-balance floor: 1,559s (CPU / 6)
    worker utilisation  : 85%
    longest single FILE : 169s

    phase     call 7,619s (81.5%) | setup 1,564-1,625s (17.4%) | teardown 108s (1.2%)

    package   3,356s 35.9% entrypoints/cli
                962s 10.3% domain/calculations
                566s  6.1% application/modelo
                374s  4.0% application/user_profile
                317s  3.4% application/ledger

    concentration  top 10 files 11.7% | top 100 51.2% | top 250 72.8%
                   files under 1s each: 2.5%

    CLI internals  spawns 824s (28.2% of CLI) over 2,541 spawns, mean 0.32s
                   in-process ~2,097s (the other 71.8%)

Slowest files (the ranking a `--durations` run should reproduce):

    169.0s  entrypoints/cli/tests/test_config_custody_profile_lifecycle.py
    127.3s  application/user_profile/tests/test_login_handover.py
    121.9s  tests/test_acceptance_wall_catalogue.py
    102.5s  entrypoints/cli/tests/test_cli_workflow_verification.py
    101.6s  entrypoints/cli/tests/test_ledger_corpus_batch_transform.py
     95.3s  tests/test_wheel_content_boundary.py

Other roots: `src/cadrumo-harness` ~93s after the descriptor memo (was 143s);
`dev` ~1,840s; `dev/packaging/tests/test_installed_oracles.py` ~244s.

## How to profile this suite without being misled

Four instrument failures are recorded in the audit. The rules they cost:

- **A `-n auto` durations entry is work PLUS contention.** One entry read 45.57s
  and was 12.94s alone. Re-measure any candidate in isolation before treating it
  as a target.
- **A ranking is not a model of cost.** `--durations=N` answers "which tests are
  slowest", never "what is the suite waiting on". Aggregate per file, per
  package and per phase before choosing a direction.
- **A repeat count is not a cost.** A directory walked 44 times cost 40ms.
  Weight any count by a measured unit cost.
- **A big SETUP figure is a bill, not a location** when the test requests a
  session-scoped fixture. The work belongs to the fixture and is already shared.
- **Before building a fixture, call the suspected shared computation twice and
  time both.** A second call at ~0s means it is already shared however the code
  looks. This settled five investigations, twice against a strong prior.
- **Validate a new instrument against a known answer.** Every counter written
  here was wrong at least once, in both directions, and always looked credible.

Operational notes: pass an explicit private `--basetemp`, because a concurrent
peer session can destroy a completed run's report through the shared
`pytest-of-<operator>` root; keep the log until the analysis is finished, because
collection costs half an hour and analysis is cheap and iterative; and use
`--tb=no`, because one full run produced a 329 MB log without it.

## What remains, and why it is not a measurement problem

Four items, each with a reproduction in the audit and none actionable without an
owner's decision:

1. Nineteen PRODUCTION `load_registry_tree` sites at ~1.05s each; the sharpest
   runs per observation save.
2. MCP cold start ~7.0s: 2.56s of import pinned by a pydantic field annotation,
   plus a 4.44s descriptor build that would need a persistence design (a stale
   tool schema is a correctness failure, not a slow start).
3. A teardown `PermissionError` on the shared pytest temp root that destroys a
   completed run's entire report.
4. `DEFAULT_WORKER_COUNT`, 6 on a 24-core box. At 85% utilisation wall clock
   tracks `CPU / workers`, so this is the ONLY remaining wall-clock lever -- and
   it is coupled to the 1,216 MB-per-worker AST prime, so raising it trades
   memory for time.

## Isolated per-file baselines

The shape above comes from `-n auto` runs, whose per-file figures carry
contention and therefore cannot support a regression CLAIM. These are
contention-free: each file run alone, `-n0`, private `--basetemp`, twice.

    file                                      run1    run2  spread   in-table
    test_config_custody_profile_lifecycle    153.7   153.2    0.3%      171.0
    test_login_handover                      115.4   116.6    1.1%      132.9
    test_acceptance_wall_catalogue            98.5    97.5    1.1%      111.7
    test_ledger_corpus_batch_transform       110.3   112.2    1.7%      103.1
    test_cli_workflow_verification           103.2   131.2   27.0%       95.0
    test_wheel_content_boundary               96.1    96.2    0.1%       94.8
    test_batch_ingest_runner                 107.4   106.5    0.8%       93.8

Six of the seven repeat within 2%, which is what makes them usable as a
baseline. `test_cli_workflow_verification` spread 27% across two runs and is
recorded as UNSTABLE rather than given a figure: comparing anything against a
number that moves by a quarter between consecutive runs would manufacture
regressions and hide real ones.

### These are NOT comparable to the per-file durations sums above

The two columns measure different things and the difference is not noise.

An isolated figure is the WALL CLOCK of a whole pytest run: collection, session
fixtures (including the ~68s AST prime where the file requests it), the tests,
and teardown. A per-file durations sum is only the recorded call/setup/teardown
phases of that file's tests, with session overhead attributed wherever it first
fired.

That is why three files read HIGHER isolated than in-table
(`test_batch_ingest_runner` 107.4 against 93.8), which no amount of contention
could explain -- the isolated run is simply paying for session work the
durations sum never counted. Compare isolated against isolated, and in-table
against in-table; a cross-comparison is meaningless in both directions.

### How to use these

Run the file alone, `-n0`, private `--basetemp`, twice. A repeat within a few
percent of the figure above is unchanged. A reproducible move beyond ~10% is a
real regression and worth a `cProfile` before anything else, because this
campaign's experience is that the cause is usually a newly unshared computation
rather than a slower one.

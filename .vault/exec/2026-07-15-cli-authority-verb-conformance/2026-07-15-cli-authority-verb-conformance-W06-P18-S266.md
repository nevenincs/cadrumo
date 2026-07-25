---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S266'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run the direct duplication runner and health-report suites and prove every unavailable or malformed execution is visibly amber rather than green

## Scope

- `src/cadrumo/tests/test_dev_audit_report.py`

## Description

- Run the duplication runner and health-report suite under an explicit execution-marker selection rather than the default lane, so the run cannot exit green on a zero-collection selection.
- Confirm a non-zero collected count before reading the result line.
- Re-run the same paths under the serial selection to prove no serial-marked case was held out of the parallel pass.
- Collect the OS-keychain remainder for the same paths to record what the agent logon cannot exercise.

## Outcome

Verdict: SATISFIED.

Command: `uv run --no-sync pytest -q -rs -p no:cacheprovider -n auto --dist=loadfile --tb=short -m "(unit or integration) and not serial and not os_keychain and not external_tool and not perf" src/cadrumo/tests/test_dev_audit_report.py`.

Collected 11, passed 11, failed 0, skipped 0. Exit line: `11 passed in 164.18s (0:02:44)`, exit code 0. HEAD at run time was `1844ef2ea03314f47bfb0cdcfaac17d0fe08be26`.

The serial selection deselected all 11 and the OS-keychain selection collected none, so the parallel pass carried the whole population: this scope has no serial-marked and no keychain-marked case, and nothing was held out of the reported result.

The run is real-behaviour rather than simulated: the suite spends nearly three minutes because it executes the duplication runner against the live tree instead of a canned payload. The amber-not-green claim is exercised across the unavailable-executable, non-zero-return, timeout, stderr, and unparseable-output paths, and the report and the direct runner are asserted to render the same typed result, so a false green cannot be produced by an execution that never completed.

## Notes

The semantic code index was degraded for the whole of this wave, reporting itself healthy while carrying roughly a fifth of the tree. No conclusion in this record rests on a semantic search result; every claim is bound to a pytest exit line or a direct read of the source.

Exit code 5 on the serial and keychain passes is the no-collection code, not a failure. The suite's own no-collection reporter prints an explicit notice that a green result there means the selection matched nothing, which is what was observed and is why the parallel pass carries the verdict.

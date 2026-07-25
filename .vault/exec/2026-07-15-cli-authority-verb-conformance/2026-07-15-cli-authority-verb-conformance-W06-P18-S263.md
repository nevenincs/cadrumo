---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S263'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run filed single, bulk, source, history-ordering, and strict IVA suites against real persisted observations and artefacts

## Scope

- `src/cadrumo/application/live/tests/`

## Description

- Run the whole live application suite under an explicit execution-marker selection covering both lanes, rather than only the three named subject suites.
- Confirm a non-zero collected count before reading the result line.
- Re-run the same scope under the serial selection to prove no serial-marked case was held out.
- Collect the OS-keychain remainder for the same scope.

## Outcome

Verdict: SATISFIED.

Command: `uv run --no-sync pytest -q -rs -p no:cacheprovider -n auto --dist=loadfile --tb=short -m "(unit or integration) and not serial and not os_keychain and not external_tool and not perf" src/cadrumo/application/live/tests`.

Collected 185, passed 185, failed 0, skipped 0. Exit line: `185 passed in 56.04s`, exit code 0. HEAD at run time was `f939f3b473032fd8af27876a4fdd2c65d0d5e102`.

The serial selection and the OS-keychain selection both collected nothing in this scope, so the parallel pass carried the whole population and nothing was held out of the reported result.

The three route policies the Step names are covered as distinct behaviours rather than as one shared path: fail-fast on the single and source routes, best-effort accumulation on the bulk route, identical latest-record selection and deterministic history ordering across all three, and the separate strict IVA compensation persistence path preserved rather than folded in.

## Notes

The semantic code index was degraded for the whole of this wave, reporting itself healthy while carrying roughly a fifth of the tree. No conclusion in this record rests on a semantic search result.

The scope was run whole rather than narrowed to the three named subjects, so the result also covers the rest of the live application surface.

Exit code 5 on the serial and keychain passes is the no-collection code, not a failure.

---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:39b3283b76ddf01a0081b91507afa307b21d7c3fddf7911ee3950a3c6bc22094'
step_id: 'S179'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run auth and certificate suites against real storage and provider boundaries

## Scope

- `src/cadrumo/application/auth/tests/`

## Description

- Run the auth and certificate suites under an explicit execution-marker selection covering both the unit and integration lanes, so the run cannot exit green on a zero-collection selection.
- Confirm a non-zero collected count before reading the result line.
- Re-run the same scope under the serial selection to prove no serial-marked case was held out of the parallel pass.
- Collect the OS-keychain remainder for the same scope to record what the agent logon cannot exercise.

## Outcome

Verdict: SATISFIED.

Command: `uv run --no-sync pytest -q -rs -p no:cacheprovider -n auto --dist=loadfile --tb=short -m "(unit or integration) and not serial and not os_keychain and not external_tool and not perf" src/cadrumo/application/auth/tests`.

Collected 185, passed 185, failed 0, skipped 0. Exit line: `185 passed in 49.98s`, exit code 0. HEAD at run time was `1844ef2ea03314f47bfb0cdcfaac17d0fe08be26`.

The serial selection and the OS-keychain selection both collected nothing in this scope, so the parallel pass carried the whole population and no case was silently held out of the reported result.

## Notes

The semantic code index was degraded for the whole of this wave, reporting itself healthy while carrying roughly a fifth of the tree. No conclusion in this record rests on a semantic search result.

This scope carries live peer work: the auth package facade, the session module, and one auth test module were uncommitted at run time, and an untracked auth test module was present. The suite is green with that work in the tree, but the result therefore describes the working tree rather than the committed tree alone.

Exit code 5 on the serial and keychain passes is the no-collection code, not a failure.

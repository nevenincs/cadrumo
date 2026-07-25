---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S180'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run ledger attach, atomic invoice-link, LLM split inheritance, and failure-rollback suites and prove no generic evidence bypass or partial child commit can execute

## Scope

- `src/cadrumo/application/ledger/tests/`

## Description

- Run the whole ledger application suite under an explicit execution-marker selection covering both lanes, rather than only the four named subject suites.
- Confirm a non-zero collected count before reading the result line.
- Re-run the same scope under the serial selection to prove no serial-marked case was held out.
- Collect the OS-keychain remainder for the same scope.

## Outcome

Verdict: SATISFIED.

Command: `uv run --no-sync pytest -q -rs -p no:cacheprovider -n auto --dist=loadfile --tb=short -m "(unit or integration) and not serial and not os_keychain and not external_tool and not perf" src/cadrumo/application/ledger/tests`.

Collected 442, passed 442, failed 0, skipped 0. Exit line: `442 passed in 71.73s (0:01:11)`, exit code 0. HEAD at run time was `f6449026877811c46e9311270b6d95c2f50c8849`.

The serial selection and the OS-keychain selection both collected nothing in this scope, so the parallel pass carried the whole population and nothing was held out of the reported result.

The atomicity claims are carried by real rollback proofs rather than by assertion of intent: the split suites induce two genuinely different failure paths, read back the persisted catalogue and the persisted event history, and assert equality with the pre-attempt state, so a partial child commit would surface as an extra row or an extra event rather than passing silently.

## Notes

The semantic code index was degraded for the whole of this wave, reporting itself healthy while carrying roughly a fifth of the tree. No conclusion in this record rests on a semantic search result.

The scope was run whole rather than narrowed to the four named subjects, so the result also covers the rest of the ledger application surface.

Exit code 5 on the serial and keychain passes is the no-collection code, not a failure.

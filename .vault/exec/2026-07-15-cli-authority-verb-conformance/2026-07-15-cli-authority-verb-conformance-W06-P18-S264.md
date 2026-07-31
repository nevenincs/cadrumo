---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:2da094399ddbcfbc73c4e9de1fa63306a6d3c4bedf5ec8b4fa307124f054fb1a'
step_id: 'S264'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run the typed LLM review workflow and both CLI routing modes against real persistence and subprocess model boundaries

## Scope

- `src/cadrumo/application/ledger/tests/`
- `src/cadrumo/entrypoints/cli/tests/`

## Description

- Select the review-workflow suites and both CLI routing suites named by the implementing Step, rather than the two whole directories the scope line names, since those directories are separately and wholly covered by the ledger and CLI Steps of this same phase.
- Run that selection under an explicit execution-marker selection covering both lanes.
- Confirm a non-zero collected count before reading the result line.
- Collect the serial and OS-keychain remainders for the same selection.

## Outcome

Verdict: SATISFIED.

Command: `uv run --no-sync pytest -q -rs -p no:cacheprovider -n auto --dist=loadfile --tb=short -m "(unit or integration) and not serial and not os_keychain and not external_tool and not perf"` over the twelve ledger review-workflow suites and the five CLI ledger routing suites.

Collected 79, passed 79, failed 0, skipped 0. Exit line: `79 passed in 24.14s`, exit code 0. HEAD at run time was `82a04ead90bef5de5ae2e2970648c32aac9be03c`. The serial and OS-keychain selections both collected nothing.

Both routing modes are covered as distinct invocation origins rather than as one path, and the suggestion side is driven through the real proposer seam with a canned proposal payload, so the model subprocess is not called while the persistence path under test stays entirely real. No test double stands in for a repository, an attachment store, or the event history.

The whole of the ledger application directory named in the scope line was separately run green in this same phase at 442 passed, and the whole of the CLI test directory is covered by its own Step of this phase, so nothing in the scope line is left unrun by this narrowing.

## Notes

The semantic code index was degraded for the whole of this wave, reporting itself healthy while carrying roughly a fifth of the tree. No conclusion in this record rests on a semantic search result.

Exit code 5 on the serial and keychain passes is the no-collection code, not a failure.

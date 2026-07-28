---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S187'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run documented-command path and argument conformance against the live tree

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py`

## Description

Run documented-command path and argument conformance against the live CLI tree, then
attribute the residual failure.

## Outcome

FAILED, peer-owned and not attributable to this feature's surface.

Command: `uv run --no-sync pytest -q -rs -n0 -m "" -p no:cacheprovider
src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py`.
Collected 352, 351 passed, 1 failed, exit line `1 failed, 351 passed in 7.44s`, exit code 1, at
HEAD `1844ef2ea0`. Reproduced on a second run.

The one failure reports a command path that does not resolve in the live CLI, against a blocked
frame reason line in the Modelo 390 records-audit sequence contract. That line is an UNCOMMITTED
working-tree edit by a concurrent campaign; the committed line it replaces carries no CLI token.

Proof, obtained without touching the tree: the line parser was fed both spellings directly. The
committed line parses to nothing. The uncommitted line parses to a cited command whose verb
tokens are the prose words of the refusal explanation, because the reason text contains the
literal product token and the parser anchors on that token anywhere in the line.

Re-run before reporting, at HEAD `593559067c`, many commits later: identical result,
`1 failed, 351 passed in 6.76s`, the same sequence-contract case. The offending edit is STILL
uncommitted at that HEAD, so the failure is standing peer working-tree state rather than a moment
that has passed.

## Notes

This exposes a fragility in the instrument as well as peer churn. The parser deliberately
skips capture and expect frame lines on the stated grounds that they carry no CLI token. Blocked
reason lines are free prose and can carry that token in an ordinary English sentence, so the same
assumption does not hold and the parser reads a refusal explanation as an invocation. The
sequence-contract grammar owner should exclude blocked reason text from invocation extraction.
Until then any campaign writing an honest blocker reason that names the CLI reddens this gate.

The remaining 351 cases pass, so path and argument conformance over the live tree is otherwise
clean.

The semantic code index was degraded throughout this Phase: the service reported `Source code sections: 466` against 3982 tracked Python files while declaring its code generation succeeded. No absence recorded here rests on a semantic miss.

## Re-measurement at HEAD bc80aa2808

SATISFIED. The previously uncommitted peer edit that caused the single failure was committed
and its sequence-contract grammar corrected by the time of this re-run. Command:
`uv run --no-sync pytest -m integration src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py`.
Collected 354, 354 passed, exit line `354 passed in 9.21s`, exit code 0, at HEAD `bc80aa2808`.
Two tests were added to the suite since the original reading (354 vs 352), consistent with new
documented verbs landing. No failures. The feature surface is clean.

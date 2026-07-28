---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S186'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Compare the materialized tree with the accepted additions and removals and fail on unplanned leaf loss

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py`

## Description

Compare the materialised tree against the accepted additions and removals and fail on
unplanned leaf loss.

Run the root-grammar invariants suite with markers unpinned and no xdist workers.

## Outcome

SATISFIED.

Command: `uv run --no-sync pytest -q -rs -n0 -m "" -p no:cacheprovider
src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py`.
Collected 17, 17 passed, exit line `17 passed in 7.35s`, exit code 0, at HEAD `1844ef2ea0`.

No unplanned leaf loss against the accepted grammar.

## Notes

A first run at HEAD `482c41c59` reported `4 failed, 13 passed` from the same auth
error-code registry race described in the S185 record. The suite passed unchanged once the peer
commit settled.

The semantic code index was degraded throughout this Phase: the service reported `Source code sections: 466` against 3982 tracked Python files while declaring its code generation succeeded. No absence recorded here rests on a semantic miss.

## Re-measurement at HEAD bc80aa2808

SATISFIED. Command: `uv run --no-sync pytest -m integration
src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py`.
Collected 17, 17 passed, exit line `17 passed in 17.20s`, exit code 0, at HEAD `bc80aa2808`.
Same count as the original reading; no retired verbs re-mounted.

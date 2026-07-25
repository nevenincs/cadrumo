---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S185'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Materialize the complete lazy CLI tree in a fresh process and assert every leaf path is unique

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_lazy_command_tree.py`

## Description

Materialise the complete lazy CLI tree in a fresh process and assert leaf-path uniqueness.

Run the lazy-command-tree suite with markers unpinned so its integration-marked cases are
actually selected, and with no xdist workers. Then re-materialise the tree independently at a
much later HEAD and diff the two dumps.

## Outcome

SATISFIED, and confirmed as a stable tree property rather than a single-HEAD reading.

Command: `uv run --no-sync pytest -q -rs -n0 -m "" -p no:cacheprovider
src/cadrumo/entrypoints/cli/tests/test_lazy_command_tree.py`.
Collected 8, 8 passed, exit line `8 passed in 21.09s`, exit code 0, at HEAD `1844ef2ea0`.

Independent confirmation: the tree was re-materialised in a fresh subprocess at HEAD
`7f8af66d3f`, many commits later, reporting `LEAVES: 289` and `DUPES: 0`. A diff against the
coordinator dump taken at the start of the Phase is EMPTY, so 289 unique leaves is a property of
the tree across a wide commit span and not a reading of one moment.

## Notes

A first run at HEAD `482c41c59` reported `3 failed, 5 passed`. Every failure was the same
mid-flight error: a base-error subclass in the auth session module carried no error-code registry
entry, because a concurrent campaign landed the class and its registry row in separate moments.
The suite passed unchanged once that peer commit settled. Peer churn, not an owner-surface defect.

A naive Typer-to-click walk of this tree yields one leaf and completes without error. The
materialiser is the only honest way to reach the tree, and that false-green shape is exactly what
this Step exists to catch.

The semantic code index was degraded throughout this Phase: the service reported
`Source code sections: 466` against 3982 tracked Python files while declaring its code
generation succeeded. No absence recorded here rests on a semantic miss.

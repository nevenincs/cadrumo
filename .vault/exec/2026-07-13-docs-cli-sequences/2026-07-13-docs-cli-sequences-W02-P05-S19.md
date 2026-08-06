---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:0971051f0555af8d900b804000c84ca829a3759e7cca22ed74391b63d1c97f3d'
step_id: 'S19'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

# Verify the whole engine test suite (parser, runner, comparison, CLI, anti-tautology) passes green with no mocks or skips

## Scope

- `dev/docs/sequences/tests`

## Description

- Run the whole engine suite — parser and seeds (unit), runner, golden store and comparison, refresh/check CLI, and the executor-level mask-honesty gate (integration) — in one pass: 89 tests green.
- Confirm ruff lint, ruff format, and ty type-check clean across `dev/docs/sequences/` and `dev/docs/tests/test_sequence_goldens.py`.
- Confirm the suite carries no mocks, stubs, patches, skips, or xfail markers: every integration test executes the real CLI in a real-crypto hermetic sandbox; every divergence case mutates a real committed artifact or a real envelope document.

## Outcome

The W02 execution engine is complete and green end to end: grammar parsing, hermetic execution with capture threading, committed goldens, masked comparison with live semantic expectations, the CLI-owned refresh/check surface, and the anti-tautology gate — the foundation W03's two build-gate surfaces wire onto without re-implementing anything.

## Notes

Peer WIP observed but untouched during this phase: uncommitted docstring-example edits in `dev/docs/sequences/_golden_store.py` and a staged `docs/tutorials -> docs/how-to` page move belong to a concurrent docs campaign; explicit-pathspec commits kept them out of this feature's history.

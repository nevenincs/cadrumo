---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-10'
modified: '2026-06-10'
step_id: 'S06'
related:
  - "[[2026-06-10-cli-operator-surface-plan]]"
---




# run the documented-command conformance gate and the new D5 gate to confirm zero drift across hint strings and enum-choice sets

## Scope

- `src/aeat/entrypoints/cli/tests`

## Description

Ran the new D5 self-referential-string gate and the existing documented-command
conformance gate together against a HEAD-consistent CLI tree.

## Outcome

All 46 tests green: 8 D5 gate tests (hint-string classes + enum-choice surfaces)
plus 38 documented-command conformance tests. The doclink `--source` and verify
`--select` offenders enumerate as fixed under the gate; the eight genuine F5
error-registry suggestion drifts surfaced by the gate were corrected to
resolvable forms. Locale gates (`scaffold --check`, parity, translation-honesty)
green.

## Notes

A concurrent peer `OutputLanguageOpt` migration across the modelo CLI cluster
(`_modelo_cli_support.py`, `_modelo_work_calculate_cli.py`,
`_modelo_work_revision_cli.py`, `_modelo_work_runs_cli.py`) left the working tree
mid-refactor and un-importable, so the live-tree gates cannot collect in the
current shared state. The 46-green result was obtained by temporarily restoring
that cluster to HEAD (safe compare-aside per the worktree-safety rule), running
the gates, and restoring peer WIP byte-for-byte. The gates will collect normally
once the peer commits its `OutputLanguageOpt` migration.



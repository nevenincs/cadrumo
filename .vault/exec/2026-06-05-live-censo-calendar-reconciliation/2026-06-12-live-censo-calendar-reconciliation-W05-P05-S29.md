---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S29'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# W05.P05.S29 - Live command-tree pull-only drift guard

## Description

- Re-verify the live authenticated read CLI surface after backend drift and Period stringification work.
- Track the user-requested `pull` versus `pull-all` consistency check in the live-censo calendar plan.
- Guard the full `app live` Typer command tree against reintroducing `pull-all` or legacy `capture-all` commands.

## Outcome

`test_registry_cli.py` now includes a recursive command-tree walker for `TyperGroup` nodes and a regression test that walks the materialized `app live` subtree. The test fails if any descendant command is named `pull-all` or `capture-all`, and it asserts the required `filed pull` and `expedientes pull` commands remain present.

Literal source scans of active source found `pull-all` and `capture-all` only in the registry guard assertions, not in live command registrations. Historical vault documents still mention the old names and are intentionally not source behavior.

## Verification

- `vaultspec-rag search --timeout 600 "CLI verb drift pull pull-all live censo filed history notifications justificante"` returned the dedicated CLI pull/file ADR, research, plan, and earlier live-censo pull-only execution records.
- `uv run ruff check src/aeat/entrypoints/cli/tests/test_registry_cli.py` passed.
- `uv run pytest src/aeat/entrypoints/cli/tests/test_registry_cli.py -m integration -q` passed with 55 tests.
- `rg -n -F "pull-all" src/aeat/entrypoints src/aeat/application src/aeat/domain` found only the guard assertions in `test_registry_cli.py`.
- `rg -n -F "capture-all" src/aeat/entrypoints src/aeat/application src/aeat/domain` found only the guard assertion in `test_registry_cli.py`.
- `vaultspec-code-reviewer` reviewed S29 and returned PASS, with residual risk limited to future hidden/non-Typer aliases.

## Live Verification Status

This step verifies the command surface without initiating an authenticated AEAT session. Full live pull execution remains tracked by W04.P04.S10 and W04.P04.S11 because it depends on creating or selecting a profile whose tax ID matches the authenticated AEAT identity.

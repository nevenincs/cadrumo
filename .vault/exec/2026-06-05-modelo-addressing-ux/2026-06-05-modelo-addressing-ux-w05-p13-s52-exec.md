---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S52'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W05.P13.S52 Centralized Addressing Verification

Scope: run focused application, CLI, resume, export, project, compare, reconcile, locale, architecture, and docs conformance tests.

## Description

- Run focused application work-addressing, selector, and workflow resume tests.
- Run focused CLI natural-key work, resume, export, compare, projection, and reconcile tests.
- Run architecture boundary tests including the new centralized-addressing guard.
- Run locale scaffold and audit checks.
- Run docs conformance tests with the `docs` marker.
- Fix one invalid placeholder command in `docs/USERDOCS-KICKOFF-BRIEF.md` so docs conformance reflects the live CLI surface.

## Outcome

Focused verification passed across application, CLI, architecture, locale, RAG, exact discovery, and docs conformance lanes.

## Notes

The docs edit was a minimal conformance correction to an internal kickoff brief, not a rewrite of user-facing tutorial content.

Post-closure validation found `_modelo_work_revision_cli.py` still called `get_work_unit` directly for Modelo 202 modality metadata. That was repaired by routing through `resolve_modelo_work_unit_for_operator_target`; scoped Ruff and architecture/resume workflow tests passed afterward. `test_cli_module_size.py` still reports unrelated `_app_live.py` and `_ledger.py` budget drift outside this feature surface.

---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S22'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

# OPERATOR-VISIBLE: reconcile the calc pull --compute verb (G2) with the one produce-bound-casilla-values-from-sources story, separating the Sheets-transport pull from the compute multiplexing per aeat-cli-pull-and-file-standard, as one atomic commit

## Scope

- `author through the locale CLI (cli.config.google.sync.calc.pull*) and sweep the runtime write-policy allowlist`
- `error-registry default_suggestion`
- `cross-period next_action builders`
- `curated operator help`
- `and envelope command= identifiers`
- `regen docs-scaffold + locale scaffold in the same commit`
- `collect-only clean and the two conformance gates green before commit`
- `apply-cached own-only`
- `abort-on-WIP`
- `src/aeat/entrypoints/cli/_config/_google_sync_calc.py`
- `src/aeat/application/storage_write_policy.py`
- `src/aeat/core/errors/_registry.py`
- `src/aeat/application/operator_surface/_help.py`

## Description

- Reconcile the landed G2 implementation from commit `03ddcff732`, which removes the `calc pull --compute` multiplexing and introduces the sibling `config google sync calc compute` read-only compute verb.
- Confirm the live `config google sync calc` group exposes `export`, `verify`, `pull`, and `compute`.
- Confirm `pull` is transport-only and `compute` carries the Sheets-edits-to-engine calculation path with envelope command `config.google.sync.calc.compute`.
- Confirm the write-policy allowlist includes the new compute verb and the schema registry covers the command.
- Re-run focused G2 evidence at HEAD.

## Outcome

- The Sheets transport and compute intents are now separate operator verbs, per `aeat-cli-pull-and-file-standard`.
- Focused verification passed:
  - `uv run --no-sync pytest -q src/aeat/entrypoints/cli/tests/test_google_payloads.py` (`7 passed`)
  - `uv run --no-sync aeat config google sync calc --help`
  - `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py` (`140 passed`)
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py` ran and failed on an unrelated docs citation in `docs/HARNESS-USERDOCS-KICKOFF-BRIEF.md` (`aeat app agent --layout plugin`), not on the calc pull/compute command paths.

## Notes

No plan step check was run in this pass. The plan file currently has non-authored WIP that only removes the template link-rule comment block, so mutating the checkbox would violate the shared-worktree abort-on-WIP rule. This record reconciles the missing exec evidence only.

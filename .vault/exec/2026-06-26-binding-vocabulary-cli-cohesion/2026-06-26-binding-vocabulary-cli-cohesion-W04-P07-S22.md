---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-07-04'
modified: '2026-07-17'
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
  - `uv run --no-sync vaultspec-rag search "google sync calc pull compute transport separate command" --type code --port 8766 --max-results 12 --timeout 30`
  - `uv run --no-sync pytest -q src/aeat/entrypoints/cli/tests/test_google_payloads.py` (`7 passed`)
  - `uv run --no-sync aeat config google sync calc --help` shows separate `pull` and `compute` commands; `pull` reads operator-edited cells to typed records and `compute` emits calculated casilla values without persistence.
  - `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py` (`140 passed`)
  - `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py` (`58 passed`)
- Blocking evidence:
  - `uv run --no-sync pytest --collect-only -q` is currently red (`12182/14891 tests collected`, `2709 deselected`, `8 errors`) because the non-authored untracked `src/aeat/_data/registry/aeat/modelos/145/` scaffold makes registry validation fail: the `2012-01-31-y-siguientes` revision has no casilla files and no official workbook parity coverage.

## Notes

No plan step check was run in this pass. The S22 target files and plan file are clean, but the step's mandatory collect-only gate is red due to unrelated non-authored registry WIP. This record reconciles current evidence without claiming closure.

## Closure retry (2026-07-04, observed at `c3cd141a0c`)

- The stale collect-only blocker is cleared in the current HEAD/worktree.
- `git grep` at HEAD confirms the split command is committed: `storage_write_policy.py` allows `config google sync calc compute`, `_google_sync_calc.py` registers `@calc_app.command("compute")`, the emitted operation/envelope is `config.google.sync.calc.compute`, and locale catalogues carry `cli.config.google.sync.calc.compute_help`.
- `uv run --no-sync aeat config google sync calc --help` shows separate `pull` and `compute` commands. `pull` reads operator-edited cells to typed records; `compute` runs the local Decimal engine and emits calculated casilla values without persistence.
- Source-only stale-command search over the operator surfaces found no `calc pull --compute`, `pull --compute`, or `config.google.sync.calc.pull_compute` hit.
- `uv run --no-sync pytest --collect-only -q` wrote full output to `C:\Users\hello\AppData\Local\Temp\aeat-d9-current-collect-retry-20260704.log` and completed clean: `12276/14908 tests collected (2632 deselected) in 109.26s`.
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py` wrote `C:\Users\hello\AppData\Local\Temp\aeat-d9-vocab-docconf-20260704.log`: `58 passed`.
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py` wrote `C:\Users\hello\AppData\Local\Temp\aeat-d9-vocab-jsonschema-20260704.log`: `140 passed`.

This retry supplies the missing clean-gate evidence for checking `W04.P07.S22`.

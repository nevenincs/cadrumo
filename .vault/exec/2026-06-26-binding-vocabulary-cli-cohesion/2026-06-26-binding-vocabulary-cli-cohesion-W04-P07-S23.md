---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S23'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

# OPERATOR-VISIBLE: align the work calculate verb (G3, the canonical aggregation-engine entry) name to the reconciled one-verb story per aeat-cli-pull-and-file-standard, as one atomic commit

## Scope

- `author through the locale CLI (cli.app.modelo.work.calculate_help) and sweep the runtime write-policy allowlist`
- `error-registry default_suggestion`
- `cross-period next_action builders`
- `curated operator help`
- `and envelope command= identifiers`
- `regen docs-scaffold + locale scaffold in the same commit`
- `collect-only clean and the two conformance gates green before commit`
- `apply-cached own-only`
- `abort-on-WIP`
- `src/aeat/entrypoints/cli/_modelo_work_calculate_cli.py`
- `src/aeat/application/storage_write_policy.py`
- `src/aeat/core/errors/_registry.py`
- `src/aeat/application/operator_surface/_help.py`

## Description

- Re-read the current `work calculate` CLI implementation after the command split and confirm it remains the canonical aggregation-engine entrypoint.
- Confirm the live command is still `aeat app modelo work calculate`, with envelope command `modelo.work.calculate` and text operation `modelo.work.calculate`.
- Confirm the runtime write-policy allowlist, error-registry default suggestions, cross-period next actions, operator help, and generated docs all still point at `work calculate`.
- Treat the current name as already aligned with the reconciled one-verb story: unlike the retired `bindings preview` and split `calc pull --compute` surfaces, `work calculate` is already the value-bearing calculation verb and does not need a rename.
- Re-run focused S23 evidence at HEAD.

## Outcome

- S23 is evidence-complete at HEAD without a code change. The command name and envelope identifier already express the canonical calculation operation, and no stale `preview` or Sheets-pull wording was found on the `work calculate` operator surface.
- Focused verification passed:
  - `uv run --no-sync vaultspec-rag search "work calculate verb one learnable verb story binding vocabulary" --type code --port 8766 --max-results 12 --timeout 30`
  - `uv run --no-sync aeat app modelo work calculate --help`
  - `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py` (`140 passed`)
  - `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py` (`58 passed`)
- Blocking evidence:
  - `uv run --no-sync pytest --collect-only -q` is currently red because non-authored untracked Modelo 145 registry scaffolding invalidates registry authority before collection completes.

## Notes

- No plan step check was run in this pass. The plan file and S23 target files are clean, but the mandatory collect-only gate is red due to unrelated non-authored registry WIP.
- No runtime, locale, docs-scaffold, or generated schema files were edited for S23 because the live surface is already aligned.

## Closure retry (2026-07-04, observed at `c3cd141a0c`)

- The stale collect-only blocker is cleared in the current HEAD/worktree.
- `git grep` at HEAD confirms `work calculate` remains the committed canonical calculation entry: `@work_app.command("calculate")`, text operation `modelo.work.calculate`, envelope command `modelo.work.calculate`, and write-policy allowlist `app modelo work calculate`.
- `uv run --no-sync aeat app modelo work calculate --help` succeeds and exposes the calculation entrypoint with binding, relation, casilla, and row input channels.
- Source-only stale-command search found no retired `bindings preview` or Sheets `pull --compute` wording on the operator vocabulary surface.
- `uv run --no-sync pytest --collect-only -q` wrote full output to `C:\Users\hello\AppData\Local\Temp\aeat-d9-current-collect-retry-20260704.log` and completed clean: `12276/14908 tests collected (2632 deselected) in 109.26s`.
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py` wrote `C:\Users\hello\AppData\Local\Temp\aeat-d9-vocab-docconf-20260704.log`: `58 passed`.
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py` wrote `C:\Users\hello\AppData\Local\Temp\aeat-d9-vocab-jsonschema-20260704.log`: `140 passed`.

This retry supplies the missing clean-gate evidence for checking `W04.P07.S23`.

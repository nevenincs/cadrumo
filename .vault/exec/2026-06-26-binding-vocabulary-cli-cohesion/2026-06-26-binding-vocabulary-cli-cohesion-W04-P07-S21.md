---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S21'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

# OPERATOR-VISIBLE: rename the bindings preview verb (G1) to a value-bearing name that says what it sources rather than the UI gesture, under aeat-cli-pull-and-file-standard, as one atomic commit

## Scope

- `author the rename through the locale CLI (python -m aeat.locales modelo / set for cli.app.modelo.bindings.preview_help and list_help) and sweep the runtime write-policy allowlist`
- `the error-registry default_suggestion fields`
- `the cross-period next_action builders`
- `the curated operator help`
- `and the envelope command= identifiers`
- `regen docs-scaffold + locale scaffold in the same commit`
- `collect-only clean and test_documented_command_conformance + test_json_schema_conformance green before commit`
- `apply-cached own-only`
- `abort-on-WIP`
- `src/aeat/entrypoints/cli/_modelo_discovery_cli.py`
- `src/aeat/application/storage_write_policy.py`
- `src/aeat/core/errors/_registry.py`
- `src/aeat/application/operator_surface/_help.py`

## Description

- Reconcile the landed G1 implementation from commit `c9d4cc09b0`, which renames the operator command from `app modelo bindings preview` to `app modelo bindings resolve`.
- Confirm the live command group exposes `list` and `resolve`, with no `preview` subcommand.
- Confirm the envelope command identifier is now `modelo.bindings.resolve` and the text operation line is `registry.modelo.bindings.resolve`.
- Confirm locale help uses `cli.app.modelo.bindings.resolve_help` across the four locale catalogues.
- Re-run focused G1 evidence at HEAD.

## Outcome

- The live CLI now names the value-bearing binding operation `resolve`, matching what it does: resolve temporary binding overrides against the registry binding surface without mutating state.
- Focused verification passed:
  - `uv run --no-sync vaultspec-rag search "modelo bindings resolve no preview command registry binding surface" --type code --port 8766 --max-results 12 --timeout 30`
  - `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_modelo_registry_surface.py -k "bindings"` (`2 passed`)
  - `uv run --no-sync aeat app modelo bindings --help` shows `list` and `resolve`, with no `preview` subcommand.
  - `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py` (`140 passed`)
  - `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py` (`58 passed`)
- Blocking evidence:
  - `src/aeat/entrypoints/cli/_modelo_discovery_cli.py`, one of S21's target files, currently carries non-authored support-matrix WIP. This pass therefore does not mutate or check S21 from that dirty target surface.
  - `uv run --no-sync pytest --collect-only -q` is currently red because non-authored untracked Modelo 145 registry scaffolding invalidates registry authority before collection completes.

## Notes

No plan step check was run in this pass. The plan file is clean, but S21's target module is dirty with non-authored WIP and the mandatory collect-only gate is red due to unrelated non-authored registry WIP. This record reconciles current evidence only.

## Closure retry (2026-07-04, observed at `c3cd141a0c`)

- The stale blocker is cleared in the current HEAD/worktree: S21's implementation targets are clean except the shared root locale catalogues, whose current diff only adds `prior_filing_observations_changed` keys and does not touch the bindings vocabulary surface.
- `uv run --no-sync aeat app modelo bindings --help` exposes `list` and `resolve`; no `preview` subcommand is present.
- Source-only stale-command search over `src/aeat/entrypoints/cli`, `storage_write_policy.py`, `core/errors/_registry.py`, `operator_surface/_help.py`, and `src/aeat/locales` found no `bindings preview`, `modelo.bindings.preview`, `calc pull --compute`, `pull --compute`, or `config.google.sync.calc.pull_compute` hit.
- `uv run --no-sync pytest --collect-only -q` wrote full output to `C:\Users\hello\AppData\Local\Temp\aeat-d9-current-collect-retry-20260704.log` and completed clean: `12276/14908 tests collected (2632 deselected) in 109.26s`.
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py` wrote `C:\Users\hello\AppData\Local\Temp\aeat-d9-vocab-docconf-20260704.log`: `58 passed`.
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py` wrote `C:\Users\hello\AppData\Local\Temp\aeat-d9-vocab-jsonschema-20260704.log`: `140 passed`.
- `uv run --no-sync python -m aeat.locales audit` reports `ok` for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

This retry supplies the missing clean-gate evidence for checking `W04.P07.S21`.

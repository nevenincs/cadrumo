---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S24'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

# Verify W04.P07 no-shift: run pytest --collect-only -q clean, test_documented_command_conformance.py and test_json_schema_conformance.py green, the locale parity + honesty gates green, and assert no dead operator instruction remains (write-policy allowlist, default_suggestion, next_action, operator help, and command= identifiers all reference the reconciled verb)

## Scope

- `src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py`
- `src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py`
- `src/aeat/locales`

## Description

- Re-run the W04.P07 verification gates at HEAD after the S21/S22/S23 evidence records.
- Confirm JSON schema conformance is green for the CLI envelope registry.
- Confirm help-language parity and help-honesty tests are green when run with the integration marker.
- Search source-only operator surfaces for stale `bindings preview`, `modelo.bindings.preview`, `pull --compute`, and stale command identifiers.
- Run full collect-only to `_scratch-wave1-d9/vocab-s24-collect-only-exact.log` and slice the saved log.
- Record the remaining blockers without checking the plan row because the current collect-only and locale gates depend on non-authored shared WIP.

## Outcome

- S24 is not checked in this pass.
- Green evidence:
  - Commit `d2dad2d789` fixes the unrelated documented-command citations by replacing the removed `aeat app agent materialise` subcommand with the live `aeat app agent --output=<dir>` callback form and by writing the plugin command as `aeat app agent --output=<dir> --layout=plugin`.
  - `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py` (`58 passed`)
  - `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py` (`140 passed`)
  - `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_output_language_parity.py src/aeat/entrypoints/cli/tests/test_language_flag_help_honesty.py` (`21 passed`)
  - Source-only stale-command searches found no stale `bindings preview` or `modelo.bindings.preview` operator command. The remaining `preview_help` hit is the unrelated ledger inventory valuation preview key, and `compute_from_pull` hits are the implementation helper used by the split `config google sync calc compute` command.
- Blocking evidence:
  - `uv run --no-sync pytest --collect-only -q` is currently red (`12182/14891 tests collected`, `2709 deselected`, `8 errors`) because the non-authored untracked `src/aeat/_data/registry/aeat/modelos/145/` scaffold invalidates registry authority. The scaffold has a `2012-01-31-y-siguientes` revision but no casilla files and no official workbook parity coverage.
  - `uv run --no-sync python -m aeat.locales audit` is currently red: all four root locale catalogues are missing `cli.app.modelo.support_matrix.help`, introduced by non-authored support-matrix WIP in `src/aeat/entrypoints/cli/_modelo_discovery_cli.py`. The same locale files also carry unrelated non-authored additions for `prior_filing_observations_changed`, so this pass does not edit or claim the locale gate.

## Notes

- No S24 plan check was run. This is a blocker/evidence record, not a closure record.
- Resolved blockers in this pass: `DFR-D9-W04-P07-S24-AGENT-DOCS-CONFORMANCE`.
- Reopened/current blocker: `DFR-D9-W04-P07-S24-PYWINTYPES-COLLECT` is no longer a pywin32 import issue, but the collect-only gate is red again due to non-authored Modelo 145 registry WIP (`DFR-D9-W04-P07-S24-M145-REGISTRY-WIP-COLLECT`).
- Remaining blocker: landed, owner-attributed locale-gate evidence for the current shared locale WIP (`DFR-D9-W04-P07-S24-SUPPORT-MATRIX-LOCALE-WIP` plus the earlier root-locale WIP lineage).
- The binding vocabulary source surface itself appears reconciled; the remaining blockers are gate-health ownership issues outside the S21/S22/S23 command vocabulary implementation.

## Retry check (2026-07-04, observed at `f4ed27f35a`)

- Authoritative plan status remains open at `W04.P07.S21`: `23/27` complete, `exec_missing_ids=[]`.
- Current collect-only gate is still red:
  `uv run --no-sync pytest --collect-only -q` wrote full output to
  `C:\Users\hello\AppData\Local\Temp\aeat-d9-retry-collect-20260704.log` and exited `2`
  (`12148/14851 tests collected`, `2703 deselected`, `8 errors`).
- The collect blocker is still the non-authored untracked Modelo 145 scaffold:
  `modelo 145 revision 2012-01-31-y-siguientes: revision must declare official workbook parity coverage`
  and `revision must declare at least one casilla`.
- Current locale audit is still red:
  `uv run --no-sync python -m aeat.locales audit` reports
  `missing cli.app.modelo.support_matrix.help` in `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- The support-matrix CLI command is now visible in the current source tree at
  `src/aeat/entrypoints/cli/_modelo_discovery_cli.py`, while the root locale files still carry
  unrelated non-authored WIP for `prior_filing_observations_changed`; this retry therefore does
  not edit locale files or check S24.

## Continuation check (2026-07-04, observed at `e8e59f9b50`)

- Locale drift had cleared in the observed tree:
  `uv run --no-sync python -m aeat.locales audit` reports `ok` for `ca.yml`, `en.yml`,
  `es.yml`, and `hu.yml`.
- W04.P07 focused gates were green in the observed tree:
  - `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py`
    (`58 passed`)
  - `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py`
    (`140 passed`)
  - `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_output_language_parity.py src/aeat/entrypoints/cli/tests/test_language_flag_help_honesty.py`
    (`21 passed`)
- Collect-only remained red in the observed tree:
  `uv run --no-sync pytest --collect-only -q` wrote full output to
  `C:\Users\hello\AppData\Local\Temp\aeat-d9-current-collect-20260704.log` and exited `2`
  (`12127/14834 tests collected`, `2707 deselected`, `8 errors`).
- The remaining S24 blocker is the non-authored untracked Modelo 145 scaffold:
  `modelo 145 revision 2012-01-31-y-siguientes: revision must declare official workbook parity coverage`
  and `revision must declare at least one casilla`.
- No S24 plan check was run because the row requires clean collect-only evidence.

## Closure retry (2026-07-04, observed at `c3cd141a0c`)

- The stale M145 collect-only blocker is cleared in the current worktree:
  `uv run --no-sync pytest --collect-only -q` wrote full output to
  `C:\Users\hello\AppData\Local\Temp\aeat-d9-current-collect-retry-20260704.log`
  and completed clean: `12276/14908 tests collected (2632 deselected) in 109.26s`.
- The locale blocker is cleared:
  `uv run --no-sync python -m aeat.locales audit` reports `ok` for `ca.yml`, `en.yml`,
  `es.yml`, and `hu.yml`.
- W04.P07 conformance gates are green:
  - `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py`
    wrote `C:\Users\hello\AppData\Local\Temp\aeat-d9-vocab-docconf-20260704.log`: `58 passed`.
  - `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py`
    wrote `C:\Users\hello\AppData\Local\Temp\aeat-d9-vocab-jsonschema-20260704.log`: `140 passed`.
  - `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_output_language_parity.py src/aeat/entrypoints/cli/tests/test_language_flag_help_honesty.py`
    wrote `C:\Users\hello\AppData\Local\Temp\aeat-d9-vocab-locale-honesty-20260704.log`: `21 passed`.
- Source-only stale-command search over the operator surfaces found no `bindings preview`,
  `modelo.bindings.preview`, `calc pull --compute`, `pull --compute`, or
  `config.google.sync.calc.pull_compute` hit.
- Current HEAD carries the reconciled commands: `app modelo bindings resolve`,
  `config google sync calc compute`, and the canonical `app modelo work calculate`.

This retry supplies the missing clean-gate evidence for checking `W04.P07.S24`.

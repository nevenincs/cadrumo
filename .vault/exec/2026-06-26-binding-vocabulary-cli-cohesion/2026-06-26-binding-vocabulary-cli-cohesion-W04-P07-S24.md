---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-07-04'
modified: '2026-07-04'
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
- Record the remaining blocker without checking the plan row because one green gate still depends on non-authored locale WIP in the shared worktree.

## Outcome

- S24 is not checked in this pass.
- Green evidence:
  - Commit `d2dad2d789` fixes the unrelated documented-command citations by replacing the removed `aeat app agent materialise` subcommand with the live `aeat app agent --output=<dir>` callback form and by writing the plugin command as `aeat app agent --output=<dir> --layout=plugin`.
  - `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py` (`58 passed`)
  - `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py` (`140 passed`)
  - `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_output_language_parity.py src/aeat/entrypoints/cli/tests/test_language_flag_help_honesty.py` (`21 passed`)
  - `uv run --no-sync pytest --collect-only -q` (`12338/15045 tests collected`, `2707 deselected`)
  - Source-only stale-command searches found no stale `bindings preview` or `modelo.bindings.preview` operator command. The remaining `preview_help` hit is the unrelated ledger inventory valuation preview key, and `compute_from_pull` hits are the implementation helper used by the split `config google sync calc compute` command.
- Blocking evidence:
  - `uv run --no-sync python -m aeat.locales audit` is green in the current worktree (`ca.yml/en.yml/es.yml/hu.yml: ok`), but `src/aeat/locales/{ca,en,es,hu}.yml` carry non-authored uncommitted additions for `prior_filing_observations_changed`. This pass therefore does not claim a landed locale-gate closure from the D9 commit set.

## Notes

- No S24 plan check was run. This is a blocker/evidence record, not a closure record.
- Resolved blockers in this pass: `DFR-D9-W04-P07-S24-PYWINTYPES-COLLECT` and `DFR-D9-W04-P07-S24-AGENT-DOCS-CONFORMANCE`.
- Remaining blocker: landed, owner-attributed locale-gate evidence for `DFR-D9-W04-P07-S24-ROOT-LOCALE-BUNDLE-SIGNING-KEYS` / the current shared locale WIP.
- The binding vocabulary source surface itself appears reconciled; the remaining blocker is landed, owner-attributed locale-gate evidence.

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
- Run full collect-only to `_scratch-wave1-d9/vocab-s24-collect-only.log` and slice the saved log after failure.
- Record the remaining blockers without checking the plan row because the plan file still carries non-authored WIP.

## Outcome

- S24 is not closable at HEAD.
- Green evidence:
  - `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py` (`140 passed`)
  - `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_output_language_parity.py src/aeat/entrypoints/cli/tests/test_language_flag_help_honesty.py` (`21 passed`)
  - Source-only stale-command searches found no stale `bindings preview` or `modelo.bindings.preview` operator command. The remaining `preview_help` hit is the unrelated ledger inventory valuation preview key, and `compute_from_pull` hits are the implementation helper used by the split `config google sync calc compute` command.
- Blocking evidence:
  - `uv run --no-sync pytest --collect-only -q` failed during collection because `src/aeat/entrypoints/mcp/tests/test_client_handshake.py` and `src/aeat/entrypoints/mcp/tests/test_serving_gates.py` import `mcp`, which imports `pywintypes`; this environment does not have `pywintypes`.
  - `uv run --no-sync python -m aeat.locales audit` failed because all four root locale catalogues are missing `errors.integrity.integrity_storage_corpus_bundle_signature` and `errors.integrity.integrity_storage_corpus_bundle_signing_key_not_found`, introduced by concurrent corpus-manifest signing work outside this D9 slice.
  - `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py` failed on unrelated `aeat app agent --layout plugin` and `aeat app agent materialise` citations in docs, not on the W04.P07 binding vocabulary commands.

## Notes

- No S24 plan check was run. This is a blocker/evidence record, not a closure record.
- Formal blockers: `DFR-D9-W04-P07-S24-PYWINTYPES-COLLECT`, `DFR-D9-W04-P07-S24-ROOT-LOCALE-BUNDLE-SIGNING-KEYS`, and `DFR-D9-W04-P07-S24-AGENT-DOCS-CONFORMANCE`.
- The binding vocabulary source surface itself appears reconciled; the blockers are cross-track gate health and shared plan-file WIP.

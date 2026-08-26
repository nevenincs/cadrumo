---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:2974decda3ae59236212efa429ca97a3d0b7c036ad827148e443ec644a595295'
step_id: 'S21'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Convert review-package import-feedback package option to a positional subject

## Scope

- `src/cadrumo/entrypoints/cli/`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_modelo_nonwork_review_package_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_google_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_app_ledger_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_ledger_corpus_journeys.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_self_referential_string_conformance.py`
- `M` `src/cadrumo/entrypoints/cli/_config/tests/test_google_command_specs.py`
- `R` `src/cadrumo/entrypoints/cli/_config/tests/test_google_sync_calc_pull_flag.py` -> `src/cadrumo/entrypoints/cli/tests/test_modelo_spreadsheet_pull_flag.py`
- `R` `src/cadrumo/entrypoints/cli/_config/tests/test_google_sync_calc_pull_observations.py` -> `src/cadrumo/entrypoints/cli/tests/test_modelo_spreadsheet_pull_observations.py`
- `R` `src/cadrumo/entrypoints/cli/tests/test_config_google_sync_calc_period.py` -> `src/cadrumo/entrypoints/cli/tests/test_modelo_spreadsheet_period.py`
- `verify:` `pytest --co over both CLI test trees` -> `pass`

## Notes

A full `pytest --co` over both CLI test trees surfaced five test modules still
importing symbols relocated in W02 and W03: the deleted `_google_sync_calc`
handler, the split `GoogleSyncCalc*` payloads, and the retired `doclink` verb.
They were swept here rather than left for W05. Three of them also belonged in a
different directory once their subject moved from `config` to `app modelo`.

---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:71159698a0a4069c81872393fc9d8a0678049cd8182334250aa7d5d1961452fd'
step_id: 'S20'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Rename config profile censo file to censo import

## Scope

- `src/cadrumo/entrypoints/cli/_config/`

## Changes

- `R` `src/cadrumo/entrypoints/cli/_config/_censo_file.py` -> `src/cadrumo/entrypoints/cli/_config/_censo_transport.py`
- `M` `src/cadrumo/entrypoints/cli/_config/_profile_command_specs.py`
- `R` `src/cadrumo/entrypoints/cli/_config/tests/test_censo_file_fact_payload.py` -> `src/cadrumo/entrypoints/cli/_config/tests/test_censo_import_fact_payload.py`
- `R` `src/cadrumo/entrypoints/cli/_config/tests/test_censo_file_verb.py` -> `src/cadrumo/entrypoints/cli/_config/tests/test_censo_import_verb.py`
- `M` `src/cadrumo/entrypoints/cli/_config/tests/test_censo_pull_verb.py`
- `verify:` `COMMAND_GRAPH rebuild (file names one leaf only)` -> `pass`

---
tags:
  - '#exec'
  - '#test-reconciliation-sweep'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:a62f0f902d3ed8ec773338eba97ced5cf0c625918e11f15096ad9d086083bfcf'
step_id: 'S12'
related:
  - "[[2026-08-28-test-reconciliation-sweep-plan]]"
---

# Repoint every module-object import that reached through the inert ledger namespace to an absolute defining-module import

## Scope

- `src/cadrumo/application/ledger/tests/`

## Changes

- `M` `src/cadrumo/llm/tests/test_local_text_reader_wiring.py`
- `M` `src/cadrumo/application/ledger/tests/test_checks_run_stamp.py`
- `M` `src/cadrumo/application/ledger/tests/test_establishment_ladder.py`
- `M` `src/cadrumo/application/ledger/tests/test_grounded_reading_wiring.py`
- `M` `src/cadrumo/application/ledger/tests/test_no_label_regex_reader.py`
- `M` `src/cadrumo/application/ledger/tests/test_preflight_iva_issue_mapping_totality.py`
- `verify:` `pytest <the five repointed modules>` -> `pass`

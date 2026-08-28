---
tags:
  - '#exec'
  - '#test-reconciliation-sweep'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:344a4b8203d844bbb0c5e039d22206579000bf2e54778700b8915ceb988b4e4b'
step_id: 'S12'
related:
  - "[[2026-08-28-test-reconciliation-sweep-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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

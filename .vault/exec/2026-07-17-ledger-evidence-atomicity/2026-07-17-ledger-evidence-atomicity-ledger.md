---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:a247c07899dbac9f551fae13c34fae3bc2f99da4fb7ed7d16ac7aa380c5147c4'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
---

# `ledger-evidence-atomicity` ledger

## Changes

- `S01` `T` `src/cadrumo/application/ledger/_actions_manual.py`
- `S02` `T` `src/cadrumo/application/ledger/tests/test_actions_update_evidence.py`
- `S03` `T` `src/cadrumo/application/ledger/tests/test_actions_create_evidence_validation.py`
- `S04` `T` `src/cadrumo/application/ledger/_actions_split_manual.py`
- `S05` `T` `src/cadrumo/application/ledger/tests/test_llm_evidence_split_apply.py`
- `S06` `T` `src/cadrumo/application/evidence/_service.py`
- `S07` `T` `src/cadrumo/entrypoints/cli/_ledger.py`
- `S08` `T` `src/cadrumo/entrypoints/cli/_modelo_audit_cli.py`
- `S09` `T` `src/cadrumo/entrypoints/cli/tests/test_ledger_link_check_verbs.py`
- `S10` `T` `src/cadrumo/entrypoints/cli/tests/test_audit_verbs.py`
- `S11` `T` `src/cadrumo/entrypoints/cli/_modelo_aux_payloads.py`
- `S12` `T` `src/cadrumo/application/operator_surface/_help.py`
- `S13` `T` `src/cadrumo/locales/en.yml`
- `S14` `T` `docs/how-to/ledger-evidence.md`
- `S15` `T` `src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py`
- `S16` `T` `src/cadrumo/application/ledger/_actions_manual.py`
- `S16` `T` `src/cadrumo/application/ledger/_actions_classification.py`
- `S16` `T` `src/cadrumo/application/ledger/_models.py`
- `S17` `T` `src/cadrumo/application/ledger/_actions_split_merge.py`
- `S18` `T` `src/cadrumo/application/invoices/_linking.py`
- `S19` `T` `src/cadrumo/application/invoices/tests/test_linking_atomicity.py`
- `S20` `T` `src/cadrumo/entrypoints/cli/_ledger_read_cli.py`
- `S20` `T` `src/cadrumo/entrypoints/cli/_ledger_payloads.py`
- `S20` `T` `src/cadrumo/entrypoints/cli/tests/test_ledger_link_check_verbs.py`
- `S21` `T` `src/cadrumo/application/ledger/_llm_classification.py`
- `S22` `T` `src/cadrumo/application/ledger/_actions_manual.py`
- `S22` `T` `src/cadrumo/application/invoices/_linking.py`
- `S22` `T` `src/cadrumo/domain/buckets/_event.py`
- `S23` `T` `src/cadrumo/core/_invoice_link.py`
- `S23` `T` `src/cadrumo/domain/invoices/_service.py`
- `S23` `T` `src/cadrumo/entrypoints/cli/_ledger_payloads.py`
- `S23` `T` `src/cadrumo/entrypoints/cli/_ledger_read_cli.py`
- `S23` `T` `src/cadrumo/application/invoices/_linking.py`

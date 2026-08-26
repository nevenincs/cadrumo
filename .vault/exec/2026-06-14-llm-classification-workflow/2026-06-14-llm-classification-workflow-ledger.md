---
tags:
  - '#exec'
  - '#llm-classification-workflow'
date: '2026-06-14'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:43235509ba8bbc7a3812b07e168dc8e0d90fe91789ee101edbe25eaf5a5b39e4'
related:
  - "[[2026-06-14-llm-classification-workflow-plan]]"
---

# `llm-classification-workflow` ledger

## Changes

- `S01` `T` `relax derive_child_amounts`
- `S01` `T` `update build_split_prompt for the single-line verdict`
- `S01` `T` `src/aeat/domain/transactions/_llm.py`
- `S01` `T` `src/aeat/application/ledger/_evidence_split.py`
- `S02` `T` `ask for it in the classification prompt when evidence is present`
- `S02` `T` `src/aeat/domain/transactions/_llm.py`
- `S03` `T` `add recommends_split`
- `S03` `T` `add apply_evidence_classification`
- `S03` `T` `guard apply_evidence_split`
- `S03` `T` `src/aeat/application/ledger/_llm_classification.py`
- `S04` `T` `add --auto-split routing into the evidence split / in-place classify`
- `S04` `T` `src/aeat/entrypoints/cli/_ledger.py`
- `S05` `T` `src/aeat/application/ledger/tests`
- `S05` `T` `src/aeat/entrypoints/cli/tests`
- `S06` `T` `update classify-with-llm how-to with the auto-split flow`
- `S06` `T` `src/aeat/locales`
- `S06` `T` `docs/how-to/classify-with-llm.md`
- `S07` `T` `src/aeat/domain/buckets/_event.py`
- `S07` `T` `src/aeat/domain/buckets/tests/test_event_catalogue.py`
- `S08` `T` `src/aeat/application/ledger/_llm_classification.py`
- `S09` `T` `src/aeat/entrypoints/cli/_ledger.py`
- `S09` `T` `src/aeat/entrypoints/cli/_ledger_llm_cli.py`
- `S09` `T` `src/aeat/entrypoints/cli/_ledger_read_cli.py`
- `S10` `T` `locales`
- `S10` `T` `how-to review-loop section`
- `S10` `T` `src/aeat/application/ledger/tests`
- `S10` `T` `src/aeat/entrypoints/cli/tests`
- `S10` `T` `src/aeat/locales`
- `S10` `T` `docs/how-to/classify-with-llm.md`
- `S11` `T` `src/aeat/entrypoints/cli/_ledger_read_cli.py`
- `S11` `T` `src/aeat/locales`
- `S11` `T` `docs/how-to/classify-with-llm.md`
- `S11` `T` `tests`
- `S12` `T` `src/aeat/entrypoints/cli/_ledger_list.py`
- `S12` `T` `src/aeat/entrypoints/cli/_ledger_read_cli.py`
- `S12` `T` `src/aeat/locales`
- `S12` `T` `tests`

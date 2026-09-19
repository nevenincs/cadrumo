---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-10'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:c48c1372157fed23cff89b257b9dbabcace3f95789640a90b310ea8ba63ea226'
related:
  - "[[2026-06-10-llm-evidence-classification-plan]]"
---

# `llm-evidence-classification` ledger

## Changes

- `S01` `T` `src/aeat/application/ledger/_evidence_input.py`
- `S02` `T` `src/aeat/application/ledger/_evidence.py`
- `S03` `T` `src/aeat/application/ledger/tests/test_evidence_input.py`
- `S04` `T` `src/aeat/core/config.py`
- `S05` `T` `src/aeat/application/ledger/_evidence.py`
- `S06` `T` `src/aeat/application/ledger/tests/test_evidence_consent.py`
- `S17` `T` `src/aeat/adapters/outbound/llm/_providers/local.py`
- `S18` `T` `src/aeat/adapters/outbound/llm/_cache.py`
- `S19` `T` `src/aeat/adapters/outbound/llm/tests/test_cache.py`
- `S20` `T` `src/aeat/adapters/outbound/llm/tests/test_local_vision.py`
- `S25` `T` `src/aeat/application/ledger/_llm_classification.py`
- `S26` `T` `src/aeat/application/ledger/_llm_classification.py`
- `S27` `T` `src/aeat/application/ledger/_llm_classification.py`
- `S28` `T` `src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py`
- `S28` `T` `src/aeat/entrypoints/cli/_ledger_payloads.py`
- `S28` `T` `src/aeat/locales/{en,es,ca,hu}.yml`
- `S29` `T` `src/aeat/application/ledger/tests/test_llm_evidence_split.py`
- `S29` `T` `src/aeat/entrypoints/cli/tests/test_ledger_llm_split.py`
- `S32` `T` `dev/docs/tests/test_docs_build.py`
- `S34` `T` `src/aeat/entrypoints/cli/_ledger.py`
- `S35` `T` `confirm the model reads the invoice and the decision stamps llm provenance`
- `S35` `T` `src/aeat/entrypoints/cli/_ledger.py`
- `S36` `T` `confirm the model selects the IVA category`
- `S36` `T` `the system derives rate/base/amount`
- `S36` `T` `and the printed-vs-derived advisory behaves`
- `S36` `T` `src/aeat/entrypoints/cli/_ledger.py`
- `S37` `T` `confirm children sum to parent`
- `S37` `T` `registry-derived numbers`
- `S37` `T` `evidence links`
- `S37` `T` `and provenance`
- `S37` `T` `src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py`

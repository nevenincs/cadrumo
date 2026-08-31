---
tags:
  - '#exec'
  - '#test-reconciliation-sweep'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:83806186989b2fd22d74f3b29b5a0b2f76324fd441fce68bbd436d7065f67f61'
step_id: 'S07'
related:
  - "[[2026-08-28-test-reconciliation-sweep-plan]]"
---

# Carry the Modelo 111 no-retenciones attestation path in the localised refusal message, following the Modelo 180 precedent, in all four catalogues

## Scope

- `src/cadrumo/application/aggregation/`

## Changes

- `M` `src/cadrumo/application/aggregation/_modelo_bindings.py`
- `M` `src/cadrumo/locales/en/common.yml`
- `M` `src/cadrumo/locales/es/common.yml`
- `M` `src/cadrumo/locales/ca/common.yml`
- `M` `src/cadrumo/locales/hu/common.yml`
- `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_source_mesh_calculate.py`
- `verify:` `pytest dev/locales/tests/test_locale_translation_honesty.py` -> `pass`

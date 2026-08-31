---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:5e19c8f3c36b86b60f9d2fdc15ae0c6c07faeba0bf19928da48f16f618dce80b'
step_id: 'S212'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# `ci-lane-deconflation` execution record: `P05.S212`

## Scope

- `P05.S212`

## Changes

- `M` `src/cadrumo/domain/iva/classification.py`
- `A` `src/cadrumo/domain/iva/_classification_rules.py`
- `M` `.vault/plan/2026-08-05-ci-lane-deconflation-plan.md`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S212.md`

## Notes

- `uv run --no-sync ruff check src/cadrumo/domain/iva/classification.py src/cadrumo/domain/iva/_classification_rules.py` emitted `All checks passed!` (exit 0); `uv run --no-sync ruff format --check src/cadrumo/domain/iva/classification.py src/cadrumo/domain/iva/_classification_rules.py` emitted `2 files already formatted` (exit 0).
- `uv run --no-sync python -c "from cadrumo.domain.iva.classification import classify_iva; from cadrumo.domain.iva import classification; print(classify_iva.__module__); print(len(classification._CLASSIFICATION_RULES))"` emitted `cadrumo.domain.iva.classification` and `21` (exit 0).
- `uv run --no-sync pytest --collect-only -q src/cadrumo/domain/iva/tests/test_classification.py src/cadrumo/domain/iva/tests/test_party_fact_split.py src/cadrumo/domain/iva/tests/test_intra_community_identification_axis.py src/cadrumo/domain/iva/tests/test_outbound_service_localisation.py src/cadrumo/domain/iva/tests/test_oss.py src/cadrumo/domain/iva/tests/test_place_of_supply_manual_oracle.py` collected 138 tests (exit 0); the matching focused run emitted `138 passed in 23.11s` (exit 0).
- `uv run --no-sync pytest -q src/cadrumo/application/invoices/tests/test_party_fact_reporting_parity.py src/cadrumo/application/invoices/tests/test_m349_clave_follows_the_classifier.py src/cadrumo/application/ledger/tests/test_classification_assembly.py` emitted `41 passed in 14.50s` (exit 0).
- `uv run --no-sync python -c "from dev.audit.size_budget import measure_module_lines; measured=measure_module_lines(); key='src/cadrumo/domain/iva/classification.py'; print(f'{key}: {measured[key]} lines; default module budget 1250; exit 0')"` emitted `src/cadrumo/domain/iva/classification.py: 1014 lines; default module budget 1250; exit 0`; no policy or baseline changed.

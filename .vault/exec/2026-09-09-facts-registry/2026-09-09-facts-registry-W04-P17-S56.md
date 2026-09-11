---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:692765cc846f94317d8f33f49a071ff1b9fe704a70651707902fb18945d4b587'
step_id: 'S56'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# `facts-registry` execution: `W04.P17.S56`

## Scope

- `dev/registry/compiler/iva.py and dev/registry/tests and src/cadrumo/domain/iva and src/cadrumo/_data/registry/aeat/iva`

## Changes

- `M` `dev/registry/analysis/facts_iva_retirement.toml`
- `D` `dev/registry/compiler/iva.py`
- `D` `dev/registry/tests/test_iva_rate_candidate_refusals.py`
- `M` `dev/registry/tests/test_iva_rate_provider.py`
- `D` `src/cadrumo/_data/registry/aeat/iva/rates.toml`
- `D` `src/cadrumo/_data/registry/aeat/iva/recargo-rates.toml`
- `M` `src/cadrumo/application/aggregation/tests/test_oss_ioss.py`
- `M` `src/cadrumo/core/tests/test_resources.py`
- `M` `src/cadrumo/domain/invoices/tests/test_models.py`
- `M` `src/cadrumo/domain/iva/lookup.py`
- `M` `src/cadrumo/domain/iva/rates.py`
- `M` `src/cadrumo/domain/iva/saturation.py`
- `M` `src/cadrumo/domain/iva/tests/test_legal_basis_rate_grounding.py`
- `M` `src/cadrumo/domain/iva/tests/test_rates.py`
- `M` `src/cadrumo/domain/iva/tests/test_rates_temporal.py`
- `M` `src/cadrumo/domain/iva/tests/test_recargo_rate_applied_rate_lookup.py`
- `M` `src/cadrumo/domain/iva/tests/test_saturation.py`
- `verify:` `uv run pytest -q dev/registry/tests/test_iva_rate_provider.py dev/registry/tests/test_iva_recargo_provider.py dev/registry/tests/test_iva_provider_grounding.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/domain/iva/rates.py` -> `pass`
- `verify:` `uv run python -m compileall -q src/cadrumo/domain/iva/rates.py` -> `pass`

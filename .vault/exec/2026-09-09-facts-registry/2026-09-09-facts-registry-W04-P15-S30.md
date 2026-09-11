---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:4c8fda9b817946cbec36bf05cffccbd696b879cecdd6cd421e5b622f73aff6ad'
step_id: 'S30'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# `facts-registry` execution: `W04.P15.S30`

## Scope

- `src/cadrumo/_data/registry/aeat/facts and src/cadrumo/_data/registry/aeat/iva and dev/registry/compiler/fact_providers.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/facts/schema.py`
- `A` `src/cadrumo/_data/registry/aeat/facts/0062-iva-rate-schedule.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0063-iva-recargo-by-applied-rate.toml`
- `M` `dev/registry/compiler/fact_providers.py`
- `M` `dev/registry/analysis/facts_wave2_provider_handoff.toml`
- `M` `dev/registry/tests/test_fact_providers.py`
- `M` `dev/registry/tests/test_facts_wave2_provider_handoff.py`
- `M` `dev/registry/tests/test_wave2_fact_provider_handoff.py`
- `M` `dev/registry/tests/test_iva_provider_grounding.py`
- `M` `dev/registry/tests/test_iva_rate_provider.py`
- `M` `dev/registry/tests/test_iva_recargo_provider.py`
- `verify:` `uv run pytest -q dev/registry/tests/test_fact_providers.py dev/registry/tests/test_facts_wave2_provider_handoff.py dev/registry/tests/test_wave2_fact_provider_handoff.py dev/registry/tests/test_iva_provider_grounding.py dev/registry/tests/test_iva_rate_provider.py dev/registry/tests/test_iva_recargo_provider.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/domain/calculations/registry/facts/schema.py dev/registry/compiler/fact_providers.py dev/registry/tests/test_fact_providers.py dev/registry/tests/test_facts_wave2_provider_handoff.py dev/registry/tests/test_wave2_fact_provider_handoff.py dev/registry/tests/test_iva_provider_grounding.py dev/registry/tests/test_iva_rate_provider.py dev/registry/tests/test_iva_recargo_provider.py` -> `pass`

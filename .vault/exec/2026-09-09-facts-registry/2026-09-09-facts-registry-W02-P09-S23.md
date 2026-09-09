---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:8fdc18555348d869ccedcf0889eab97501a106a727c3fad066bf9bd2121e26e2'
step_id: 'S23'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# Verify provider compilation exact resolution and provenance at the Wave 2 handoff

## Scope

- `src/cadrumo/domain/calculations/registry/tests`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/facts/tests/test_authority_enrollment.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_wave2_fact_provider_handoff.py`
- `A` `dev/registry/analysis/facts_wave2_provider_handoff.toml`
- `A` `dev/registry/tests/test_facts_wave2_provider_handoff.py`
- `verify:` `uv run pytest -q <focused Wave 2 provider boundary and parity tests>` -> `pass`
- `verify:` `uv run ruff check <S23 test paths>` -> `pass`
- `verify:` `uv run ty check <S23 test paths>` -> `pass`
- `verify:` `uv run pytest -n 0 dev/registry/tests/test_facts_wave2_provider_handoff.py -q` -> `pass`

---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:8cf3f7b47bc739e717eadfd875de44f6185784eb28b41f08933569dff54eec6a'
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
- `verify:` `uv run pytest -q <focused Wave 2 provider boundary and parity tests>` -> `pass`
- `verify:` `uv run ruff check <S23 test paths>` -> `pass`
- `verify:` `uv run ty check <S23 test paths>` -> `pass`

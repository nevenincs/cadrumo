---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:5024b38735e803051fe11162eaf0f47eb483797f878fdcdd08d990e71415b184'
step_id: 'S06'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# Enroll facts in fingerprints authority identity memoisation validation and resets

## Scope

- `src/cadrumo/domain/calculations/registry`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `M` `src/cadrumo/domain/calculations/registry/_validate.py`
- `M` `src/cadrumo/domain/calculations/registry/_validation_memoization.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/providers.py`
- `A` `src/cadrumo/domain/calculations/registry/facts/validation.py`
- `A` `src/cadrumo/domain/calculations/registry/facts/tests/test_authority_enrollment.py`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `A` `.vault/exec/2026-09-09-facts-registry/2026-09-09-facts-registry-W01-P02-S06.md`
- `verify:` `uv run pytest -n 0 src/cadrumo/domain/calculations/registry/facts/tests/test_authority_enrollment.py -q` -> `pass`
- `verify:` `uv run pytest -n 0 src/cadrumo/domain/calculations/registry/facts/tests/test_authority_catalogue.py::test_validated_authority_exposes_the_attached_fact_catalogue -q` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/domain/calculations/registry/authority.py src/cadrumo/domain/calculations/registry/_validate.py src/cadrumo/domain/calculations/registry/_validation_memoization.py src/cadrumo/domain/calculations/registry/facts/providers.py src/cadrumo/domain/calculations/registry/facts/validation.py src/cadrumo/domain/calculations/registry/facts/tests/test_authority_enrollment.py` -> `pass`
- `verify:` `uv run ty check src/cadrumo/domain/calculations/registry/authority.py src/cadrumo/domain/calculations/registry/_validate.py src/cadrumo/domain/calculations/registry/_validation_memoization.py src/cadrumo/domain/calculations/registry/facts/providers.py src/cadrumo/domain/calculations/registry/facts/validation.py src/cadrumo/domain/calculations/registry/facts/tests/test_authority_enrollment.py` -> `pass`

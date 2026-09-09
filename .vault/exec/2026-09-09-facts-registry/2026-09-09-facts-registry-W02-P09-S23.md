---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:0219eed4b7125422ffdc0612ac91cb4711d7668ed6c5b6c9ceb1169d2bb9e55f'
step_id: 'S23'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Verify provider compilation exact resolution and provenance at the Wave 2 handoff

## Scope

- `src/cadrumo/domain/calculations/registry/tests`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/facts/tests/test_authority_enrollment.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_wave2_fact_provider_handoff.py`
- `verify:` `uv run pytest -q <focused Wave 2 provider boundary and parity tests>` -> `pass`
- `verify:` `uv run ruff check <S23 test paths>` -> `pass`
- `verify:` `uv run ty check <S23 test paths>` -> `pass`

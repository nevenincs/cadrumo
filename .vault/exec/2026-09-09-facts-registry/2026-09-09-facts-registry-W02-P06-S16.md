---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:aa0d649c58d29887a49f51ec3c0319b31b90b1028f8701544fe8bb41312f8267'
step_id: 'S16'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Register statutory category profiles and dated caps

## Scope

- `src/cadrumo/domain/categories/registry.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/facts/providers.py`
- `M` `src/cadrumo/domain/categories/registry.py`
- `A` `src/cadrumo/domain/categories/tests/test_fact_provider.py`
- `A` `src/cadrumo/_data/registry/aeat/legal/category-profile-sources.toml`
- `verify:` `uv run pytest -q src/cadrumo/domain/categories/tests/test_fact_provider.py src/cadrumo/domain/categories/tests/test_registry.py src/cadrumo/domain/categories/tests/test_statutory_cap_schedule.py src/cadrumo/domain/calculations/registry/facts/tests/test_providers.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/domain/categories/registry.py src/cadrumo/domain/categories/tests/test_fact_provider.py src/cadrumo/domain/calculations/registry/facts/providers.py` -> `pass`

---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:745b35a90379c96ecd21fc485d0701c69c573116bd54e1595aff3c0ee1036853'
step_id: 'S20'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Register statutory scalars schedules and classifications

## Scope

- `src/cadrumo/core/external_constants.py`

## Changes

- `A` `src/cadrumo/domain/calculations/registry/facts/statutory_constants.py`
- `A` `src/cadrumo/domain/calculations/registry/facts/tests/test_statutory_constants_provider.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/providers.py`
- `A` `src/cadrumo/_data/registry/aeat/legal/statutory-constant-sources.toml`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `A` `.vault/exec/2026-09-09-facts-registry/2026-09-09-facts-registry-W02-P08-S20.md`
- `verify:` `uv run pytest -n 0 src/cadrumo/domain/calculations/registry/facts/tests/test_statutory_constants_provider.py src/cadrumo/domain/calculations/registry/facts/tests/test_providers.py -q` -> `pass`
- `verify:` `uv run pytest -n 0 src/cadrumo/domain/calculations/registry/facts/tests/test_convenio_provider.py::test_convenio_provider_references_validate_through_full_authority -q` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/domain/calculations/registry/facts/statutory_constants.py src/cadrumo/domain/calculations/registry/facts/tests/test_statutory_constants_provider.py src/cadrumo/domain/calculations/registry/facts/providers.py` -> `pass`
- `verify:` `uv run ty check src/cadrumo/domain/calculations/registry/facts/statutory_constants.py src/cadrumo/domain/calculations/registry/facts/tests/test_statutory_constants_provider.py src/cadrumo/domain/calculations/registry/facts/providers.py` -> `pass`

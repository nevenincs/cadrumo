---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:b18b3c7fd1ae4a9cc92e088418d30fceb48d447f864d2ce20e41c36272b5c1f4'
step_id: 'S14'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Register recargo by applied rate and operation date

## Scope

- `src/cadrumo/domain/iva/recargo_equivalencia.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/facts/providers.py`
- `A` `src/cadrumo/domain/calculations/registry/facts/tests/test_iva_recargo_provider.py`
- `M` `src/cadrumo/domain/iva/recargo_equivalencia.py`
- `verify:` `uv run python -m pytest -n 0 src/cadrumo/domain/calculations/registry/facts/tests/test_iva_recargo_provider.py src/cadrumo/domain/iva/tests/test_recargo_rate_applied_rate_lookup.py src/cadrumo/domain/iva/tests/test_recargo_equivalencia.py -q` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/domain/iva/recargo_equivalencia.py src/cadrumo/domain/calculations/registry/facts/providers.py src/cadrumo/domain/calculations/registry/facts/tests/test_iva_recargo_provider.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/domain/iva/recargo_equivalencia.py src/cadrumo/domain/calculations/registry/facts/providers.py src/cadrumo/domain/calculations/registry/facts/tests/test_iva_recargo_provider.py` -> `pass`

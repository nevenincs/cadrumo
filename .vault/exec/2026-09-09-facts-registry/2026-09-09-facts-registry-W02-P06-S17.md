---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:6c6266b633eb20cc67ead09355313f935093310ec1d01883fec578d4cf01c817'
step_id: 'S17'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Register classified legal calendar and deadline facts

## Scope

- `src/cadrumo/domain/deadlines`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/facts/providers.py`
- `M` `src/cadrumo/domain/deadlines/festivos.py`
- `A` `src/cadrumo/domain/deadlines/tests/test_fact_provider.py`
- `verify:` `uv run pytest -q src/cadrumo/domain/deadlines/tests/test_fact_provider.py src/cadrumo/domain/deadlines/tests/test_festivos.py src/cadrumo/domain/calculations/registry/facts/tests/test_providers.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/domain/deadlines/festivos.py src/cadrumo/domain/deadlines/tests/test_fact_provider.py src/cadrumo/domain/calculations/registry/facts/providers.py` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/domain/deadlines/festivos.py src/cadrumo/domain/deadlines/tests/test_fact_provider.py` -> `pass`

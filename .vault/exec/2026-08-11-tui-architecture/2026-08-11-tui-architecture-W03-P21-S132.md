---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:c02af6ea63fdaf5eef1e7f6b6d6101ebf06411fc37157c7a082fbe5381b7f8a4'
step_id: 'S132'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Define the strict ModeloEditContractV1 family covering version and compatibility headers, read-only edit schema, ModeloEditBaselineV1, parse and preflight requests and results, scalar and repeatable-row intents, guarded apply request, mutation capability, typed refusal, and immutable result receipt

## Scope

- `src/cadrumo/application/modelo/_edit_models.py`

## Changes

- `A` `src/cadrumo/application/modelo/_edit_models.py`
- `A` `src/cadrumo/application/modelo/tests/test_edit_models.py`
- `M` `src/cadrumo/core/identity/__init__.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_edit_models.py -q -n 0 -m integration` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo/_edit_models.py src/cadrumo/application/modelo/tests/test_edit_models.py src/cadrumo/core/identity/__init__.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/modelo/_edit_models.py src/cadrumo/application/modelo/tests/test_edit_models.py src/cadrumo/core/identity/__init__.py` -> `pass`

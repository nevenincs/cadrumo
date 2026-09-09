---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:6ee4846f34697c25c53b465d205be1840e6703645e4e5bac02434cf01940b339'
step_id: 'S369'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete both unwired Modelo 296 export resolvers, their private row-builder vocabulary, and the builder-only test module.

## Scope

- `Modelo 296 withholding registry bindings`
- `application row assembly tests`
- `exact unused-symbol signal`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/withholding296_bindings.py`
- `D` `src/cadrumo/domain/calculations/registry/tests/test_withholding296_row_builders.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/withholding296_bindings.py` -> `pass`
- `verify:` `uv run --no-sync pytest -n0 -m "" src/cadrumo/application/calculations/tests/test_row_set_assembly.py -q` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`

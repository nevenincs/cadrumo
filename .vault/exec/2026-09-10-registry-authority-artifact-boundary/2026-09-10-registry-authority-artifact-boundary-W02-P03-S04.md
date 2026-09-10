---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:4da48acf8ce63b1643e53d0860b1e7d0ad24b22c9dfdcf17552ec51eff6b033c'
step_id: 'S04'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Remove runtime compiler cache and raw loader exposure

## Scope

- `src/cadrumo/domain/calculations/registry/loader.py`

## Changes

- `D` `src/cadrumo/domain/calculations/registry/loader.py`
- `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `A` `dev/registry/compiler/`
- `M` `dev/registry/pipeline/authority_publication.py`
- `M` `dev/registry/pipeline/cli.py`
- `M` `src/cadrumo/domain/iva/_grounding.py`
- `M` `src/cadrumo/domain/iva/catalogue.py`
- `A` `src/cadrumo/domain/iva/tests/test_artifact_backed_grounding.py`
- `verify:` `uv run pytest src/cadrumo/domain/calculations/registry/tests/test_bundled_authority_artifact_runtime.py dev/registry/tests/test_authority_publication.py src/cadrumo/domain/iva/tests/test_artifact_backed_grounding.py -q` -> `pass`

---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:bad51f101a4b2db9bb573977713aa19b96df99404fa36e393dd20d414ff95903'
step_id: 'S03'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
---
<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Replace bundled source compilation with artifact loading

## Scope

- `src/cadrumo/domain/calculations/registry/authority.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `M` `src/cadrumo/domain/calculations/registry/authority_artifact.py`
- `D` `src/cadrumo/domain/calculations/registry/loader.py`
- `A` `dev/registry/compiler/authority.py`
- `verify:` `uv run pytest -n 0 src/cadrumo/domain/calculations/registry/tests/test_authority_artifact.py src/cadrumo/domain/calculations/registry/tests/test_bundled_authority_artifact_runtime.py` -> `pass`

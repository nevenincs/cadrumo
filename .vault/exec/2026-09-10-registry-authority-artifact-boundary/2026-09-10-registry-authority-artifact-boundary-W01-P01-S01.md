---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:db1ac3f7c8970c0129383fa10bc2764f256646af9dfe5544744f1e7af9f4b0b5'
step_id: 'S01'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Implement the artifact reader and writer contract

## Scope

- `src/cadrumo/domain/calculations/registry/authority_artifact.py`

## Changes

- `A` `src/cadrumo/domain/calculations/registry/authority_artifact.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_authority_artifact.py`
- `verify:` `uv run pytest src/cadrumo/domain/calculations/registry/tests/test_authority_artifact.py -q` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/domain/calculations/registry/authority_artifact.py src/cadrumo/domain/calculations/registry/tests/test_authority_artifact.py` -> `pass`
- `verify:` `uv run ty check src/cadrumo/domain/calculations/registry/authority_artifact.py` -> `pass`

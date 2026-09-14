---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:08b93a0fe6c87534bbabc57d13d80f1efeb5e3ee86a3b96efe64f8c5a936255b'
step_id: 'S13'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Define the component/codec contract and public typed query, generation-pin and profile create/decode context signatures, with representative fake behavior for the consumer lanes

## Scope

- `src/cadrumo/domain/calculations/registry/authority_artifact.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/authority_artifact.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/authority_fakes.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_authority_component_contract.py`
- `verify:` `uv run --no-sync pytest -n 0 -m unit src/cadrumo/domain/calculations/registry/tests/test_authority_component_contract.py -q` -> `pass`
- `verify:` `uv run --no-sync ruff check ...` -> `pass`
- `verify:` `uv run --no-sync ty check ...` -> `pass`

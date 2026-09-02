---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:8ae0e0cb7e608583c526cced7c441231cfa7bbbfc2f8399591c28caa0ceca286'
step_id: 'S38'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---

# Remove the publication-input dispatcher left without a consumer

## Scope

- `dev/packaging/publication_inputs.py`

## Changes

- `D` `dev/packaging/publication_inputs.py`
- `D` `dev/packaging/tests/test_publication_inputs.py`
- `verify:` `uv run --no-sync pytest -q -n0 --collect-only dev/packaging/` -> `pass`

## Notes

The module was not merely unreachable, it could no longer be imported: it binds
`claimed_channels` out of the download matrix, and that function went when the tier and
availability model was deleted. Its whole purpose was deriving dispatch inputs for
`publish-release.yml`, a workflow the adopted release path replaced.

The name also appears in the registry tests, where `_publication_inputs` is a local
fixture builder with no relationship to this module. Read in context rather than counted,
so the deletion is not driven by a collision.

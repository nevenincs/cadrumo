---
tags:
  - '#exec'
  - '#data-provenance-consolidation'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:a67383c4eaa0d1f74f9c0c28f572cc34cef7a1f590b2411fc983aac189b62b47'
step_id: 'S24'
related:
  - "[[2026-09-10-data-provenance-consolidation-plan]]"
---

# Verify the authority publish workflow rejects a divergent record-design source binding while preserving the prior artifact

## Scope

- `dev/registry/tests/test_authority_publication.py`

## Changes

- `M` `dev/registry/compiler/authority.py`
- `M` `dev/registry/tests/test_authority_publication.py`
- `M` `src/cadrumo/tests/registry_snapshot.py`
- `M` `dev/registry/tests/_referential_integrity_support.py`
- `verify:` `uv run pytest -n0 dev/registry/tests/test_authority_publication.py -q` -> `pass`

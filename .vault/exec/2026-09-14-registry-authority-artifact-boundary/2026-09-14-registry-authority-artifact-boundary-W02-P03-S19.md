---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:998084371cb22fc2cd4beae8a39206e67677a620b780be72cea358b9326beadd'
step_id: 'S19'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---

# Add operation/component identity checks, resource leases and at most four exclusive connection checkouts per reader; release before dependency decoding and distinguish cutover from corruption

## Scope

- `src/cadrumo/domain/calculations/registry/authority_store.py`

## Changes

- `A` `src/cadrumo/domain/calculations/registry/authority_store.py`
- `A` `dev/registry/tests/test_authority_database.py`
- `verify:` `checkpoint A focused source/enrollment and component selection` -> `pass`

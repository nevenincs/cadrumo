---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:26e0c57ad3fea413daeba154040b5ea99406b410cbd0794abf030b171784e6d1'
step_id: 'S314'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the persisted-version literal enrollment census and embedded constructor strings

## Scope

- `persisted version inventory test`
- `focused session persistence contracts`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/tests/test_persisted_version_literal_inventory.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/adapters/outbound/aeat/auth/tests/test_persisted_session_validation.py src/cadrumo/adapters/outbound/aeat/auth/tests/test_persisted_session_instant_contract.py src/cadrumo/adapters/persistence/storage/tests/test_profile_login_session_adapter.py src/cadrumo/adapters/persistence/storage/custody/tests/test_acceleration_receipt_roundtrip.py` -> `pass`

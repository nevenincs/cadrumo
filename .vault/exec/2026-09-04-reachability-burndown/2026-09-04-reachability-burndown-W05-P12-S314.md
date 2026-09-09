---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:16f910d22911cfd59cf5f0283bbfa729a9f3fb725aca44125ee902800f04538c'
step_id: 'S314'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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

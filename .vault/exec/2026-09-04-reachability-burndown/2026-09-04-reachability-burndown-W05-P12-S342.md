---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:b6926fb8324b1645229e59a071a95c447a341c8e453a0c08060720dcccdcc667'
step_id: 'S342'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the sensitive-persistence source-policy engine and its hand-maintained surface, call-site, and exception inventories.

## Scope

- `sensitive persistence policy test`
- `behavioral storage security suites`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/adapters/persistence/storage/tests/test_sensitive_persistence_policy.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/tests/test_secure_sql.py src/cadrumo/domain/invoices/tests/test_secure_storage_roundtrip.py src/cadrumo/domain/submission/tests/test_secure_storage_roundtrip.py src/cadrumo/application/modelo/tests/test_review_package.py src/cadrumo/application/user_profile/tests/test_recovery_custody.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`

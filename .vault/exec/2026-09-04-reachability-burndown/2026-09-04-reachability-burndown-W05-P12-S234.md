---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:587f036451951032805923230122596684f5096a27c472ce01b68998e4b182cf'
step_id: 'S234'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Remove the unused profile-bundle import-event metadata that describes an event no production path emits, while retaining the accepted bundle deserializer authority.

## Scope

- `src/cadrumo/application/user_profile/bundle.py`

## Changes

- `M` `src/cadrumo/application/user_profile/bundle.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/user_profile/bundle.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 --basetemp .tmp/pytest-s234 src/cadrumo/application/user_profile/tests/test_bundle_encryption_kdf_window.py src/cadrumo/domain/user_profile/tests/test_portable_export_schema.py src/cadrumo/domain/user_profile/tests/test_portable_export_outer_instant.py src/cadrumo/domain/user_profile/tests/test_portable_export_instant_contract.py src/cadrumo/core/tests/test_persisted_version_single_declaration.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

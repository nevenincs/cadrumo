---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S372'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S372 - Close AFR-270 for user-profile schema loader

Scope: close `AFR-270` for `src/aeat/domain/user_profile/_loader.py` with signal
`plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`.

## Description

- Audited `_loader.py` for raw filesystem exceptions, plaintext schema reads,
  active-profile resolution, secure-storage access, settings/environment access, and
  exception swallowing.
- Hardened the pre-read `stat()` step so missing or inaccessible schema files raise
  `UserProfileSchemaLoadError` instead of raw `OSError` subclasses.
- Updated `UserProfileSchemaLoadError` to carry the localized
  `errors.fail.fail_user_profile_schema_load` key explicitly.
- Routed read and validation failures through a structured helper with `operation`,
  `path`, and `schema` context while preserving exception chaining for OS/TOML/pydantic
  causes.
- Added real-behavior tests for missing schema paths and malformed schema tables.
- Repaired an over-deep relative import in the user-profile registry-contract test that
  blocked the focused schema verification suite.
- Closed `W12.P26.S372` through `vaultspec-core vault plan step check` and updated
  the `AFR-270` register status to `closed`.

## Outcome

`AFR-270` is closed. `_loader.py` still reads the bundled user-profile schema TOML, but
all loader failure paths now surface through the domain AEAT exception hierarchy with a
localized message key and structured context. The module does not own profile bucket
storage, secure-object repositories, active profiles, or runtime persistence.

Validation passed:

- `uv run --no-sync ruff check src/aeat/domain/user_profile/_loader.py src/aeat/domain/user_profile/_errors.py src/aeat/domain/user_profile/tests/test_schema.py src/aeat/domain/user_profile/tests/test_registry_contract.py`
- `uv run --no-sync pytest -q src/aeat/domain/user_profile/tests/test_schema.py src/aeat/domain/user_profile/tests/test_registry_contract.py`
- `uv run --no-sync -q python -m aeat.locales audit`

## Notes

No locale YAML was edited. The existing registered `FAIL_USER_PROFILE_SCHEMA_LOAD`
message key already covers this loader boundary.

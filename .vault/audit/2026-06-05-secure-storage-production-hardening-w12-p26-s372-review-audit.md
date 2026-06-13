---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W12-P26-S372]]'
---

# `secure-storage-production-hardening` `W12.P26.S372` Review

## S372-001 | FIXED | Pre-read stat no longer leaks raw filesystem errors

`load_user_profile_schema()` previously called `resolved.stat()` before the TOML loader
wrapped `OSError` failures. Missing or inaccessible paths now raise
`UserProfileSchemaLoadError` with `operation=stat`, preserving the original exception
as `__cause__`.

## S372-002 | PASS | Schema load failures are localized AEAT errors

`UserProfileSchemaLoadError` derives from `AeatError` through `UserProfileError` and now
sets `translated_message="errors.fail.fail_user_profile_schema_load"`. The registered
error code remains `FAIL_USER_PROFILE_SCHEMA_LOAD`.

## S372-003 | PASS | Read and validation failures carry structured context

The loader routes read and validation failures through a single helper that records
`operation`, `path`, and `schema`. Validation failures do not swallow causes; pydantic
validation errors remain chained.

## S372-004 | PASS | No secure-storage ownership is duplicated

`_loader.py` reads only the bundled schema TOML or an explicit caller-supplied schema
path. It does not resolve active profiles, inspect storage runtime, construct
secure-object repositories, read environment variables, or persist profile data.

## S372-005 | FIXED | Focused registry-contract test import regressed

The verification suite initially failed because `test_registry_contract.py` used
over-deep relative imports. The imports now target the production `core.resources` and
`domain.calculations.registry` modules.

## S372-006 | PASS | Validation

- `uv run --no-sync ruff check ...` passed for the loader, errors, schema tests, and
  registry-contract tests.
- `uv run --no-sync pytest -q ...` passed 11 user-profile schema/registry tests.
- `uv run --no-sync -q python -m aeat.locales audit` passed.

Disposition: close `AFR-270`; plaintext schema-file failures now cross the public
boundary as localized, structured AEAT errors.

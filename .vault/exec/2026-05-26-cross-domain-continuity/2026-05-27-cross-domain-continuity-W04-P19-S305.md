---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
step_id: S305
plan: "[[2026-05-26-cross-domain-continuity-plan]]"
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity W04.P19.S305 — _refuse_duplicate_tax_id warn-and-continue

## What was done

Fixed the fail-closed `except Exception` handler in
`_refuse_duplicate_tax_id` inside `ProfileRepository`. Before this fix,
any unreadable bucket encountered during the NIF uniqueness scan raised
`UserProfileValidationError` and aborted the entire `profile create`
call, even when the operator was registering a completely different
taxpayer with a distinct NIF. A single torn or temporarily unreadable
profile blocked the creation of any new profile.

### Code change

`src/aeat/application/user_profile/_profile_repository.py` — in
`_refuse_duplicate_tax_id`:

- Changed `except Exception as exc: raise UserProfileValidationError(...)` to
  `except Exception: _log.warning(..., exc_info=True); continue`.
- Only a confirmed duplicate NIF against a *readable* profile now raises
  `ProfileAlreadyRegisteredError`; unreadable profiles are warned about and
  skipped.
- Docstring updated to document the warn-and-continue behaviour.

### Test changes

`src/aeat/application/user_profile/test_profile_repository.py`:

- Added `_create`, `_load`, `_delete`, `_select`, `_rename` helpers that
  each wrap their call in the appropriate `profile_create_storage_span` /
  `profile_storage_session` context so the test storage session is active
  for the call.
- Migrated all existing test bodies from direct `repository.method()` calls
  to the helpers.
- `test_create_succeeds_with_different_nif_when_scan_hits_unreadable_profile`:
  tears one bucket's manifest so the scan hits a read error, then asserts
  a second profile with a distinct NIF is created successfully. Fails
  against the pre-fix code.
- `test_create_still_refuses_duplicate_nif_against_readable_profiles`:
  anti-tautology check — tears a bystander profile, then asserts
  `ProfileAlreadyRegisteredError` still fires for a genuine NIF collision
  against the readable profile. Proves the warn-and-continue change did
  not disable duplicate detection.

## Gate results

- `pytest test_profile_repository.py`: 17 passed
- `ruff check` + `ruff format --check`: clean

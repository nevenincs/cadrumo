---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:6d0eff2fe654a28d65158dec8542b85884d442448e09b36956aa53dd291d4407'
step_id: 'S94'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Re-point the login session module's storage-root helper onto effective_storage_root once S10 lands, deleting the local function that reads only the settings default with no override parameter

## Scope

- `src/cadrumo/application/user_profile/_login_session.py`

## Description

- Confirm the login-session gating test suite is green before touching the file.
- Delete the local `_storage_root()` helper (a bare settings-default read with no override parameter) and its four call sites, replacing each with `effective_storage_root()`.
- Add the `effective_storage_root` import; keep the existing `load_settings` import since it is still used elsewhere in the module.

## Outcome

Landed in commit `eb0d94e22d`. Gated by `test_login_session.py` (7 tests, green before and after) and the full `application/user_profile` package (367 tests, green after). No override parameter existed on this site, so no behavioural change beyond routing through the shared accessor.

## Notes

None.

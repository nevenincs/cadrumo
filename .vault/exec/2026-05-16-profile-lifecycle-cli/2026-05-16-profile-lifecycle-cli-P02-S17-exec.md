---
tags:
  - "#exec"
  - "#profile-lifecycle-cli"
date: "2026-05-17"
modified: '2026-05-17'
step_id: S17
related:
  - "[[2026-05-16-profile-lifecycle-cli-plan]]"
---

# `profile-lifecycle-cli` `P02.S17`

Deleted the `WorkflowState.active_profile` field. The active profile
now lives exclusively in the operator-facing precedence chain
(Settings override > plaintext pointer file). Every reader of the
field migrated to `resolve_active_bucket_id` across three earlier
commits in this phase. The resolver's third rung (the state
fallback) is removed in the same commit as the field.

- Modified: `src/aeat/application/workflow/_models.py`
- Modified: `src/aeat/application/user_profile/_orchestration.py`
- Modified: `src/aeat/application/user_profile/test_orchestration.py`
- Modified: `src/aeat/application/workflow/test_state_persistence_roundtrip.py`
- Modified: `src/aeat/application/workflow/test_transaction_catalogue_resolution.py`
- Modified: `src/aeat/application/config_reset.py`
- Modified: `src/aeat/application/setup_reset.py`
- Modified: `src/aeat/application/test_config_reset.py`
- Modified: `src/aeat/application/test_setup_reset.py`
- Modified: `src/aeat/application/wizard/test_status.py`
- Modified: `src/aeat/entrypoints/cli/_config/test_apoderado.py`
- Modified: `src/aeat/application/conftest.py` (use
  `monkeypatch.setenv` for storage-root isolation; `override_settings`
  in an autouse fixture would snapshot Settings ahead of any later
  fixture's env mutation, masking nested test isolation).

## Description

Three earlier commits in P02 already migrated every reader of
`state.active_profile` to call `resolve_active_bucket_id(state)`.
This commit performs the deletion:

- `WorkflowState.active_profile: str | None` field removed.
- `WorkflowState.active_profile_record()` and
  `active_profile_bucket_id()` properties remain on the record but
  consult the resolver internally (already migrated).
- `resolve_active_bucket_id`'s third rung (the state fallback)
  removed; the function now reads Settings then the pointer file
  only.
- Every `model_copy(update={"active_profile": ...})` write site
  removed: `register_active_profile`, `select_profile`,
  `remove_active_profile`, `config_reset.py`, `setup_reset.py`,
  test fixtures.
- Every `WorkflowState(active_profile=...)` construction site
  removed: roundtrip test, transaction-catalogue-resolution test.
- The transaction-catalogue routing test now uses
  `override_settings(aeat_active_profile=...)` to drive the
  precedence chain per-assertion.

The `application/conftest.py` autouse fixture flipped from
`override_settings(aeat_local_storage_root=tmp_path)` back to
`monkeypatch.setenv("AEAT_LOCAL_STORAGE_ROOT", ...)`. The
`override_settings` form snapshotted Settings at fixture-setup
time, masking later `monkeypatch.setenv` calls in dependent test
fixtures (e.g., `test_persistence.py`'s `AEAT_DATABASE_URL`
override). `BaseSettings` re-reads env on every `Settings()`
instantiation, so the setenv form composes correctly under nested
fixtures.

## Tests

`uv run --no-sync pytest src/aeat/application/workflow/
src/aeat/application/user_profile/ src/aeat/application/auth/ -q
-k "not test_details_dict_str_str_accepted and not
test_details_rejects_non_string_value and not test_ensure_"` →
157 passed, 6 deselected. The three `test_ensure_session`
deselected failures are a pre-existing pydantic forward-ref bug
on `AuthenticatedAeatSessionResult`; the two `test_details_*`
deselected failures are a pre-existing `WorkflowStep.details`
typed-model issue. Both reproduce on plain HEAD without P02
changes.

---
tags:
  - "#exec"
  - "#profile-lifecycle-cli"
date: "2026-05-16"
modified: '2026-05-16'
step_id: S16
related:
  - "[[2026-05-16-profile-lifecycle-cli-plan]]"
---

# `profile-lifecycle-cli` `P02.S16`

Deleted the `Settings.aeat_default_profile_name` field. Added the
operator-vocabulary `Settings.aeat_active_profile` field as the
canonical per-shell override for the active-profile precedence
chain. Re-keyed seven production callers off the deleted field
through a new `require_active_bucket_id` helper. Routed every
test fixture through `override_settings()` (the central Settings
injection mechanism) instead of `monkeypatch.setenv`.

- Modified: `src/aeat/core/config.py`
- Modified: `src/aeat/application/workflow/_models.py`
- Modified: `src/aeat/application/auth/_sessions.py`
- Modified: `src/aeat/application/auth/_acquisition_lock.py`
- Modified: `src/aeat/adapters/outbound/aeat/auth/_authenticator.py`
- Modified: `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`
- Modified: `src/aeat/adapters/outbound/aeat/browser/_factory.py`
- Modified: `src/aeat/adapters/outbound/aeat/sede/_declarations.py`
- Modified: `env/.env.example` (key rename to `AEAT_ACTIVE_PROFILE`)
- Modified: `src/aeat/entrypoints/cli/test_registry_cli.py`
- Modified: `src/aeat/application/auth/test_*` (3 files, fixtures
  flipped to `override_settings`)
- Modified: `src/aeat/adapters/outbound/aeat/auth/test_*` (3 files)
- Modified: `src/aeat/adapters/outbound/aeat/sede/test_groi_check_live.py`
- Modified: `src/aeat/application/user_profile/test_orchestration.py`
- Created: `src/aeat/application/conftest.py` (autouse
  `_isolated_aeat_root` fixture redirecting
  `Settings.aeat_local_storage_root` to tmp_path for every
  application-layer test)

## Description

`Settings.aeat_default_profile_name` (default `"default"`) was used
by seven production sites as a filename / Profile-name string for
auth session paths, lock files, and the SEDE declarations Profile
record. The field had no operator-meaningful default and a brittle
hard-coded fallback. It is deleted in this commit.

The replacement is a two-rung mechanism:

1. `Settings.aeat_active_profile: str | None = None` — a proper
   pydantic-settings field. `BaseSettings` auto-reads
   `AEAT_ACTIVE_PROFILE` env var; `override_settings()` from
   `core.config` is the test injection path.
2. `application/workflow/_models.require_active_bucket_id()` —
   reads `settings.aeat_active_profile`, falls back to the
   plaintext pointer file, raises `NoActiveProfileError` on
   absence. Six of the seven production sites adopt this helper.

Site seven (`browser/_factory.default_browser_session_factory`)
is reachable from the diagnostic browser-connectivity probe under
`aeat config status` and MUST NOT raise on a missing active
profile, or the operator cannot diagnose the missing-profile
condition. That site uses
`resolve_active_bucket_id() or "diagnostic-probe"` so the
connectivity probe still labels its browser session even when no
operator profile is selected.

The resolver no longer touches `os.environ` directly. Every read
of "what is the active profile" flows through Settings, satisfying
the codebase rule that production code reads config through
pydantic-settings, never naked env access (see operator memory
`settings-not-naked-env`).

Test fixtures previously set `aeat_default_profile_name="operator"`
via `Settings(...)` kwargs or `model_copy(update=...)`. After the
deletion those constructors raise `extra="forbid"` ValidationError.
The fixtures now wrap each test in
`override_settings(aeat_active_profile="operator")`. The new
application-level conftest redirects `aeat_local_storage_root` to
`tmp_path` for every test, so the orchestration's pointer-file
write inside `register_active_profile` / `select_profile` stays
in the sandbox and never bleeds into the project's real
`var/storage/` directory.

## Tests

`rm -f var/storage/active-profile && uv run --no-sync pytest
src/aeat/application/workflow/test_transaction_catalogue_resolution.py
src/aeat/application/auth/test_acquisition_lock.py
src/aeat/application/auth/test_sessions_storage_state_paths.py
src/aeat/application/auth/test_operator.py
src/aeat/application/user_profile/test_orchestration.py -q` → 23 passed.

Three `test_ensure_session.py` tests fail with a pre-existing
pydantic `AuthenticatedAeatSessionResult` forward-reference bug
(`AeatSession` is `TYPE_CHECKING`-only). The failure reproduces on
plain HEAD without any P02 changes; the bug is unrelated to this
work and should be addressed in a separate commit by the auth
maintainers.

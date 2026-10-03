---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-10-03'
body_hash: 'sha256:605f50dbf6d4f8eee491d5e4e44a456980f1056ac70fd6401326b7bbd22ccc4d'
related: []
---

# `secure-storage-production-hardening` `W12.P23.S93` Application Bootstrap Slice Review

## S93-APP-BOOTSTRAP-001 | LOW | Workflow fixture no longer clears active-profile engines

the retired test migrated the autouse fixture to `isolated_profile_storage_root` and removed the prior global `dispose_engine()` calls. The shared helper disposes only the database URL captured by its entry settings, which is the cold root fallback when no active profile is set. This test fixture then enters `profile_create_storage_span("operator")`, and `workflow_state_repository()` opens the active-profile database URL for `operator`. On teardown, the helper's `dispose_engine(settings)` does not clear that active-profile engine. The old fixture used `dispose_engine()` with no settings while the profile span was still active, clearing all cached engines after each test.

Risk: the migrated fixture still isolates data because pytest supplies a new `tmp_path`, but it no longer preserves the old resource-cleanup behavior. The stale SQLAlchemy engine can keep SQLite handles for the per-test active-profile database open, which is a Windows cleanup/flakiness risk and weakens the S93 promise that replacing local dispose wrappers with the runtime helper preserves behavior.

## S93-APP-BOOTSTRAP-002 | PASS | LOW finding resolved

The fixture now uses `isolated_profile_storage_root` for centralized profile-storage settings and file-backed custody setup while retaining a teardown-only global `dispose_engine()` after the active-profile span. The retained cleanup is not route setup and does not reintroduce explicit `aeat_database_url` wiring; it closes the active-profile engine opened after the shared helper entered.

Targeted validation passed after the repair: 16 application bootstrap tests, ruff, the route/setup shortcut scan, and whitespace checks.

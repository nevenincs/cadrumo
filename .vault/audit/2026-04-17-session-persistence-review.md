---
tags:
  - "#audit"
  - "#session-persistence"
date: "2026-04-17"
related:
  - "[[2026-04-16-session-persistence-research]]"
  - "[[2026-04-17-session-persistence-adr]]"
  - "[[2026-04-17-session-persistence-phase1-plan]]"
---

# `session-persistence` Code Review

SESS-001 | HIGH | Browser profile currently manufactures a fake storage-state file that can poison resume logic
`src/aeat/browser/profile.py:30-32` writes `{}` to `storage_state_path` whenever the file is missing, and `src/aeat/browser/session.py:128-129` then always passes that path into `browser.new_context(storage_state=...)`. For issue #192 this is a blocking defect: a brand-new profile becomes indistinguishable from a previously authenticated persisted session, and the replay path cannot tell “missing” from “present but invalid”.

SESS-002 | MEDIUM | Default browser-profile call sites disagree on the canonical persisted-state filename
`src/aeat/justificante/_verify.py:70` already uses `<profile>-storage.json`, while `src/aeat/cli/browser/health.py:107` still uses `<profile>.json`. The plan should standardize this so the authenticator, health probe, and ad hoc browser utilities all look in the same gitignored cache location.

## ADR Audit | 2026-04-17

The ADR matches issue #192 scope and is accepted as written with two mandatory implementation requirements: keep the Playwright storage-state file raw, and treat any invalid or mismatched persisted state as disposable so fresh auth can proceed without manual cleanup.

## Plan Audit | 2026-04-17

The phase-1 plan matches the current auth/browser architecture. The only required addition is that the implementation must eliminate the placeholder JSON file behavior before trusting any resume path, otherwise the resume-first `authenticate()` branch will inherit a false-positive state file.

SESS-003 | HIGH | Resume-time login failures do not invalidate the persisted storage-state pair
`src/aeat/auth/_authenticator.py:788-805` raises `_PersistedSessionInvalidError` directly when a resumed context fails the live `verify_login()` probe, but only `_raise_invalid_persisted_state()` actually deletes `storage_state` + `.meta.json`. A direct `resume_from_storage_state()` call therefore leaves known-bad session files on disk, and even the `authenticate()` fallback path only replaces them if the subsequent fresh auth succeeds. This violates the ADR invalidation rule for failed live verification and is not covered by `src/aeat/auth/test_authenticator.py`, which only exercises stale-metadata invalidation.

SESS-004 | MEDIUM | Persisted AEAT session files are not permission-hardened on Windows
`src/aeat/auth/_authenticator.py:967-972` returns immediately on non-POSIX platforms, so the sensitive Playwright `storage_state` JSON and metadata sidecar inherit whatever ACLs the working tree already has. In the current `win32` test environment that means there is no best-effort user-only protection for live AEAT cookies/local storage, and the scoped tests contain no assertion for this security contract.

## Rolling Review Update | 2026-04-17

SESS-001 | RESOLVED
`src/aeat/browser/profile.py` now creates only the parent directory, and `src/aeat/browser/session.py` only passes `storage_state` into `browser.new_context()` when a real JSON file exists. That restores the critical distinction between “no persisted session captured yet” and “persisted state exists and should be replayed”.

SESS-002 | RESOLVED
`src/aeat/cli/browser/health.py` now uses the same `<profile>-storage.json` path shape as the authenticator and justificante verifier, so the browser-facing surfaces converge on a single canonical cache filename under `settings.aeat_token_dir`.

SESS-003 | RESOLVED
`src/aeat/auth/_authenticator.py` now persists a raw Playwright storage-state JSON file plus an adjacent AEAT metadata sidecar, validates the pair by schema/hash/thumbprint/TTL, eagerly deletes invalid pairs, and falls back to a fresh handshake only when replay is unsafe. Unit coverage in `src/aeat/auth/test_authenticator.py` exercises capture, replay without a handshake, and stale-state fallback with real temp-dir file I/O.

## Verification | 2026-04-17

- `uv run pytest src/aeat/auth/test_authenticator.py src/aeat/browser/test_profile.py src/aeat/browser/test_session.py -m unit`
- `uv run ruff check src/aeat/auth/_authenticator.py src/aeat/auth/test_authenticator.py src/aeat/browser/profile.py src/aeat/browser/session.py src/aeat/browser/test_profile.py src/aeat/browser/test_session.py src/aeat/cli/browser/health.py src/aeat/justificante/_verify.py`

## Final Review Update | 2026-04-17

SESS-004 | RESOLVED
The resumed-session failure branch now invalidates the persisted storage-state pair immediately when the live login probe fails, instead of leaving known-bad artifacts on disk until some later fresh auth succeeds. Regression coverage was added in `src/aeat/auth/test_authenticator.py::test_resume_from_storage_state_invalidates_failed_live_probe`.

SESS-005 | RESOLVED
Windows runs now receive a best-effort ACL hardening pass through `icacls.exe`, and regression coverage asserts the current user remains on the temp-file ACL after the hardening step in `src/aeat/auth/test_authenticator.py::test_restrict_file_permissions_windows`.

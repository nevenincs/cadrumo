---
tags:
  - "#audit"
  - "#session-persistence"
date: "2026-04-17"
modified: '2026-04-17'
related:
  - "[[2026-04-16-session-persistence-research]]"
  - "[[2026-04-17-session-persistence-adr]]"
  - "[[2026-04-17-session-persistence-phase1-plan]]"
---

# `session-persistence` Code Review

SESS-001 | HIGH | Browser profile currently manufactures a fake storage-state file that can poison resume logic
`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/profile.py:30-32` writes `{}` to `storage_state_path` whenever the file is missing, and `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py:128-129` then always passes that path into `browser.new_context(storage_state=...)`. For issue #192 this is a blocking defect: a brand-new profile becomes indistinguishable from a previously authenticated persisted session, and the replay path cannot tell “missing” from “present but invalid”.

SESS-002 | MEDIUM | Default browser-profile call sites disagree on the canonical persisted-state filename
`src/aeat/domain/justificante/_verify.py:70` already uses `<profile>-storage.json`, while `src/aeat/entrypoints/cli/browser/health.py:107` still uses `<profile>.json`. The plan should standardize this so the authenticator, health probe, and ad hoc browser utilities all look in the same gitignored cache location.

## ADR Audit | 2026-04-17

The ADR matches issue #192 scope and is accepted as written with two mandatory implementation requirements: keep the Playwright storage-state file raw, and treat any invalid or mismatched persisted state as disposable so fresh auth can proceed without manual cleanup.

## Plan Audit | 2026-04-17

The phase-1 plan matches the current auth/browser architecture. The only required addition is that the implementation must eliminate the placeholder JSON file behavior before trusting any resume path, otherwise the resume-first `authenticate()` branch will inherit a false-positive state file.

SESS-003 | HIGH | Resume-time login failures do not invalidate the persisted storage-state pair
`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py:788-805` raises `_PersistedSessionInvalidError` directly when a resumed context fails the live `verify_login()` probe, but only `_raise_invalid_persisted_state()` actually deletes `storage_state` + `.meta.json`. A direct `resume_from_storage_state()` call therefore leaves known-bad session files on disk, and even the `authenticate()` fallback path only replaces them if the subsequent fresh auth succeeds. This violates the ADR invalidation rule for failed live verification and is not covered by `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_authenticator.py`, which only exercises stale-metadata invalidation.

SESS-004 | MEDIUM | Persisted AEAT session files are not permission-hardened on Windows
`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py:967-972` returns immediately on non-POSIX platforms, so the sensitive Playwright `storage_state` JSON and metadata sidecar inherit whatever ACLs the working tree already has. In the current `win32` test environment that means there is no best-effort user-only protection for live AEAT cookies/local storage, and the scoped tests contain no assertion for this security contract.

## Rolling Review Update | 2026-04-17

SESS-001 | RESOLVED
`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/profile.py` now creates only the parent directory, and `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py` only passes `storage_state` into `browser.new_context()` when a real JSON file exists. That restores the critical distinction between “no persisted session captured yet” and “persisted state exists and should be replayed”.

SESS-002 | RESOLVED
`src/aeat/entrypoints/cli/browser/health.py` now uses the same `<profile>-storage.json` path shape as the authenticator and justificante verifier, so the browser-facing surfaces converge on a single canonical cache filename under `settings.aeat_token_dir`.

SESS-003 | RESOLVED
`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py` now persists a raw Playwright storage-state JSON file plus an adjacent AEAT metadata sidecar, validates the pair by schema/hash/thumbprint/TTL, eagerly deletes invalid pairs, and falls back to a fresh handshake only when replay is unsafe. Unit coverage in `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_authenticator.py` exercises capture, replay without a handshake, and stale-state fallback with real temp-dir file I/O.

## Verification | 2026-04-17

- `uv run pytest src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_authenticator.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_profile.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_session.py -m unit`
- `uv run ruff check src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_authenticator.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/profile.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_profile.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_session.py src/aeat/entrypoints/cli/browser/health.py src/aeat/domain/justificante/_verify.py`

## Final Review Update | 2026-04-17

SESS-004 | RESOLVED
The resumed-session failure branch now invalidates the persisted storage-state pair immediately when the live login probe fails, instead of leaving known-bad artifacts on disk until some later fresh auth succeeds. Regression coverage was added in `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_authenticator.py::test_resume_from_storage_state_invalidates_failed_live_probe`.

SESS-005 | RESOLVED
Windows runs now receive a best-effort ACL hardening pass through `icacls.exe`, and regression coverage asserts the current user remains on the temp-file ACL after the hardening step in `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_authenticator.py::test_restrict_file_permissions_windows`.

SESS-006 | HIGH | Real BrowserSession instances cannot be torn down, so auth/resume cycles leak launched Chromium browsers
`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py:115-165` launches a Playwright `Browser` into a local `browser` variable, creates one context, and then drops the handle without storing it on `self` or exposing a `close()` method on `BrowserSession`. Meanwhile `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py:1058-1077` only tears down a browser session by calling `session.close()` when that method exists. With the real `BrowserSession` class in this branch, `AeatAuthenticator.close()` therefore closes only the context and never the underlying browser process, which is especially problematic in the new resume/invalidation loops where multiple auth attempts can occur in one run.

SESS-007 | MEDIUM | The invalidation matrix still lacks coverage for several file-integrity branches
`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py:751-769` and `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py:874-928` contain distinct invalidation branches for metadata-sidecar absence/malformed JSON, unsupported schema version, SHA-256 mismatch, and malformed Playwright payload shape (`cookies` / `origins` arrays). The scoped tests in `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_authenticator.py` now cover success, stale fallback, failed live probe, and Windows ACL hardening, but they still do not exercise those integrity branches. Given that one invalidation bug already escaped into the earlier review loop, the missing coverage here is material.

## Continuous Audit Update | 2026-04-17

SESS-006 | RESOLVED
`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py` now owns the launched Playwright `Browser` on `self`, reuses that handle for context creation, and exposes an idempotent `close()` so `AeatAuthenticator.close()` can tear the browser down instead of only closing the active context. Regression coverage in `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_session.py::test_browser_session_close_closes_owned_browser_and_is_idempotent` proves the owned browser is closed exactly once.

SESS-007 | RESOLVED
`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_authenticator.py` now drives the full persisted-session invalidation matrix with real temp-dir artifacts: missing storage file, invalid JSON, non-object JSON root, missing `cookies`, missing `origins`, missing metadata sidecar, malformed metadata JSON, unsupported schema version, SHA-256 mismatch, expired idle deadline, certificate thumbprint mismatch, certificate subject mismatch, and failed live login probe. This closes the remaining integrity-branch coverage gap in `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py`.

SESS-008 | RESOLVED
The previous Windows ACL regression test relied on `pytest.skip` outside Windows. It now runs as a best-effort cross-platform test: Windows still inspects the resulting ACL via `icacls`, and non-Windows runs assert the helper remains non-destructive. That removes the skip-based shortcut from the scoped session-persistence tests.

Final scoped verification pass succeeded:
- `uv run pytest src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_authenticator.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_profile.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_session.py -m unit`
- `uv run ruff check src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_authenticator.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/profile.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_profile.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_session.py src/aeat/entrypoints/cli/browser/health.py`

After this loop, no additional low / medium / high findings surfaced in the requested review scope (`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py`, `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_authenticator.py`, `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/profile.py`, `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py`, `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_profile.py`, `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_session.py`, `src/aeat/entrypoints/cli/browser/health.py`, and the session-persistence `.vault` artifacts).

## PR Thread Reconciliation | 2026-04-17

Gemini review threads on `wgergely/aeat#200` were checked explicitly against the current branch state.

- Gemini thread on `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py` (`TypeError` fallback in `_run_login_probe`) is addressed: the defensive `TypeError` catch was removed, and the local browser-page test doubles already honor the protocol-level `goto(..., timeout=...)` signature.
- Gemini thread on `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py` (`mkstemp` / `os.fdopen` in `_write_json_atomic`) is addressed: the writer now uses `tempfile.NamedTemporaryFile(delete=False)` with immediate `tmp_path` capture and best-effort cleanup.

Post-reconciliation verification succeeded:
- `uv run pytest src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_authenticator.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_profile.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_session.py -m unit`
- `uv run ruff check src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_authenticator.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/profile.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_profile.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_session.py src/aeat/entrypoints/cli/browser/health.py`

---
tags:
  - "#plan"
  - "#session-persistence"
date: "2026-04-17"
modified: '2026-04-17'
related:
  - "[[2026-04-17-session-persistence-adr]]"
  - "[[2026-04-16-session-persistence-research]]"
  - "[[2026-04-17-session-persistence-review-audit]]"
---

# `session-persistence` `phase1` plan

Implement persisted AEAT browser-session replay by pairing Playwright `storage_state` JSON with AEAT-side metadata, validating that pair on startup, and automatically falling back to a fresh auth flow when reuse is unsafe.

## Proposed Changes

- Remove placeholder storage-state file creation from the browser profile layer and only preload existing Playwright state files.
- Extend the authenticator with persisted-session capture, resume, validation, invalidation, and fresh-auth fallback helpers.
- Standardize all default browser-profile call sites on the `-storage.json` filename pattern under `settings.aeat_token_dir`.
- Add unit coverage for capture/resume success, invalidation on malformed or stale persisted state, and fallback into a fresh auth path without reusing the bad files.

## Tasks

- `Stop creating empty storage-state placeholder files`
- `Teach BrowserSession to preload only existing storage-state JSON`
- `Add persisted-session sidecar models and atomic file helpers`
- `Implement resume-first authenticate flow with eager invalidation`
- `Add real temp-dir unit coverage for capture, resume, and fallback`
- `Run targeted pytest and lint verification`

## Parallelization

The browser/profile path fixes and the authenticator persistence logic are tightly coupled through the storage-state contract, so the implementation should remain serial. Verification can batch the affected auth and browser test modules together once the patches settle.

## Verification

- Run `uv run pytest src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_authenticator.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_profile.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_session.py -m unit`
- Run `uv run ruff check src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_authenticator.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/profile.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_profile.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_session.py src/aeat/entrypoints/cli/browser/health.py src/aeat/domain/justificante/_verify.py`
- Re-read the rolling session-persistence review and confirm the placeholder-file and invalid-replay findings are resolved.

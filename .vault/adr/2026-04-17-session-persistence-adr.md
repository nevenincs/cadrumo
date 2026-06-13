---
tags:
  - "#adr"
  - "#session-persistence"
date: "2026-04-17"
modified: '2026-04-17'
related:
  - "[[2026-04-16-session-persistence-research]]"
  - "[[2026-04-17-aeat-access-gate-adr]]"
  - "[[2026-04-17-session-persistence-review-audit]]"
---

# `session-persistence` adr: `persist playwright storage_state with aeat metadata sidecar` | (**status:** `accepted`)

## Problem Statement

The AEAT certificate handshake and login wall are expensive and make both local runs and Playwright-backed tests slower and less stable than necessary. The auth foundation from issue #167/#181 already models a live AEAT session, but it does not yet persist a verified browser session to disk so a later process can resume it directly.

## Considerations

- The persisted artifact must remain outside git and inside the existing gitignored token/cache area.
- Playwright already defines the canonical cross-process browser-session format through `storage_state`; duplicating that schema inside AEAT code would create drift.
- AEAT-specific reuse checks require more than raw browser cookies. We must also bind the persisted state to the certificate that created it, the idle-TTL contract, and the last successful auth evidence.
- Resume must be opportunistic, not trusted blindly. Any malformed, expired, mismatched, or login-invalid persisted state must be discarded automatically and replaced with a fresh certificate-backed session.

## Constraints

- The persisted storage-state JSON must never be committed and must live under `settings.aeat_token_dir`.
- The implementation must not rely on mocks or monkey-patched global state for its core tests; disk behavior should be exercised with real temp files.
- The feature must integrate into the existing `AeatAuthenticator` boundary rather than creating a second auth stack.

## Implementation

- Use `settings.aeat_token_dir / f"{settings.aeat_default_profile_name}-storage.json"` as the canonical Playwright storage-state path unless a caller explicitly supplies another path to `resume_from_storage_state()`.
- Keep the Playwright JSON file raw and adjacent to a metadata sidecar file whose schema records:
  - `schema_version`
  - `certificate_thumbprint`
  - `certificate_subject`
  - `certificate_nif`
  - `authenticated_at`
  - `idle_deadline`
  - `storage_state_sha256`
  - `handshake`
- Extend `AeatAuthenticator` with `capture_storage_state(session)` and `resume_from_storage_state(path)`.
- `authenticate()` should attempt resume first when a persisted state is present. Only when resume is unavailable or invalid should it fall back to a fresh certificate handshake and browser auth flow.
- Browser-session creation must only preload a storage-state file when a real JSON file exists. Missing files should mean “fresh context”, not “load an empty placeholder”.
- Persisted files must be written atomically and use best-effort user-only file permissions.

## Invalidation Logic

- Invalidate and delete the persisted storage-state pair when any of the following is true:
  - the storage-state file is missing
  - the metadata sidecar is missing or malformed
  - the Playwright JSON does not have the expected top-level `cookies` and `origins` arrays
  - the storage-state SHA-256 does not match the sidecar
  - the persisted idle deadline has elapsed
  - the current loaded certificate thumbprint differs from the persisted thumbprint
  - the resumed browser context fails `verify_login()`
- After invalidation, re-run the fresh certificate-handshake path and capture a new persisted state from the resulting verified session.

## Rationale

This design keeps the persisted browser artifact compatible with Playwright while isolating AEAT-specific trust decisions into a narrow sidecar schema. It also keeps failure handling simple: a persisted state is either self-consistent and login-valid, or it is deleted and replaced.

## Consequences

- Subsequent AEAT runs can bypass the expensive handshake when the persisted session is still valid.
- The persisted session remains bound to the certificate that created it, reducing the chance of replaying state under the wrong identity.
- Corrupt or stale artifacts self-heal by being discarded and regenerated instead of poisoning future runs.

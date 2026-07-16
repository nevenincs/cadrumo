---
tags:
  - "#adr"
  - "#session-persistence"
date: "2026-04-17"
modified: '2026-07-17'
related:
  - "[[2026-04-16-session-persistence-research]]"
  - "[[2026-04-17-aeat-access-gate-adr]]"
  - "[[2026-04-17-session-persistence-review-audit]]"
  - '[[2026-07-16-protected-browser-certificate-auth-adr]]'
---

# `session-persistence` adr: `persist encrypted playwright storage_state with bound aeat metadata` | (**status:** `accepted`)

## Problem Statement

Establishing a fresh AEAT protected-browser session is expensive and makes both local runs and Playwright-backed tests slower and less stable than necessary. The auth foundation from issue #167/#181 already models a live AEAT session, but it does not yet persist a verified browser session so a later process can attempt a bound resume.

## Considerations

- The persisted artifact must remain outside git in encrypted, profile-scoped
  secure storage.
- Playwright already defines the canonical cross-process browser-session format through `storage_state`; duplicating that schema inside AEAT code would create drift.
- AEAT-specific reuse checks require more than raw browser cookies. We must also bind the persisted state to the certificate that created it, the idle-TTL contract, and the last successful auth evidence.
- Resume must be opportunistic, not trusted blindly. Any malformed, expired, mismatched, or login-invalid persisted state must be discarded automatically and replaced with a fresh certificate-backed session.

## Constraints

- Browser storage state and its metadata must be stored only through the
  encrypted session repository; plaintext token-directory JSON is forbidden.
- The implementation must not rely on mocks or monkey-patched global state for its core tests; disk behavior should be exercised with real temp files.
- The feature must integrate into the existing `AeatAuthenticator` boundary rather than creating a second auth stack.

## Implementation

- Use the active bucket's canonical certificate-session object key as the
  `storage_state_path` identity. It names encrypted repository state rather
  than a readable filesystem sidecar.
- Store the Playwright state and its metadata together inside the encrypted,
  integrity-bound current-schema envelope. The metadata records:
  - `schema_version`
  - `certificate_thumbprint`
  - `certificate_subject`
  - `certificate_nif`
  - `authenticated_at`
  - `idle_deadline`
  - `storage_state_sha256`
  - the canonical protected-resource URL
- Extend `AeatAuthenticator` with `capture_storage_state(session)` and `resume_from_storage_state(path)`.
- `authenticate()` should attempt resume first when a persisted state is present. Only when resume is unavailable or invalid should it delete that state and enter the one fresh certificate-backed protected-browser flow.
- Application orchestration supplies validated persisted state explicitly when constructing a resume context. Missing state means “fresh context”; `BrowserSession` does not discover or preload profile state implicitly.
- The encrypted repository is the sole persistence writer and retains the
  secure-storage atomicity and permissions contract.

## Invalidation Logic

- Invalidate and delete the persisted encrypted state when any of the following is true:
  - the encrypted persisted object is missing
  - its current-schema metadata is missing or malformed
  - the Playwright JSON does not have the expected top-level `cookies` and `origins` arrays
  - the storage-state SHA-256 does not match the integrity-bound metadata
  - the persisted idle deadline has elapsed
  - the current loaded certificate thumbprint differs from the persisted thumbprint
  - the resumed browser context fails `verify()`
- After structural and certificate-identity validation, resume must navigate to
  `https://www6.agenciatributaria.gob.es/wlpl/TEWV-CORE/ResumenVlt` and require a
  successful response plus the exact final scheme, host, and path. A failed
  resume is deleted before the canonical fresh path runs once.
- After invalidation, run the fresh certificate-bound context path and capture
  new state only after the same canonical protected-resource assertion succeeds.

## Rationale

This design keeps the persisted browser artifact compatible with Playwright while binding AEAT-specific trust metadata inside one encrypted current-schema envelope. It also keeps failure handling simple: persisted state is structurally valid, identity-bound, and confirmed by the canonical protected-resource assertion, or it is deleted before a single fresh attempt.

## Consequences

- Subsequent AEAT runs can avoid fresh login work when the persisted session still passes every resume gate and the canonical protected-resource assertion.
- The persisted session remains bound to the certificate that created it, reducing the chance of replaying state under the wrong identity.
- Corrupt or stale artifacts self-heal by being discarded and regenerated instead of poisoning future runs.

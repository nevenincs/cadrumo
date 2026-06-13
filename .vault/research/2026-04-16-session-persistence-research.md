---
tags:
  - "#research"
  - "#session-persistence"
date: "2026-04-16"
modified: '2026-04-16'
related:
  - "[[2026-04-17-aeat-access-gate-adr]]"
  - "[[2026-04-17-session-persistence-review-audit]]"
---

# `session-persistence` research

## Scope

Investigate how the AEAT browser/auth stack can persist authenticated Playwright state across processes without leaking secrets into git or coupling the design to an HTTPX-specific cookie file format.

## Findings

- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py` already defines the correct boundary for live AEAT access: a loaded certificate, a Playwright-backed browser context, and a frozen `AeatSession` record with an 18-minute idle TTL.
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py` already accepts a `Profile.storage_state_path` and passes that path into `browser.new_context(storage_state=...)`, which is the Playwright-supported way to preload cookies and origin storage into a fresh browser context.
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/profile.py` currently creates the parent directory and writes `{}` into the storage-state file when it is missing. That placeholder is unsafe for this feature because it makes every new browser context look like it has a resumable state file even when no authenticated session has been captured yet.
- `src/aeat/domain/justificante/_verify.py` already uses the path pattern `settings.aeat_token_dir / f"{settings.aeat_default_profile_name}-storage.json"`, while `src/aeat/entrypoints/cli/browser/health.py` still uses `f"{settings.aeat_default_profile_name}.json"`. The feature needs one canonical filename.
- Playwright `BrowserContext.storage_state()` serializes cookies plus origin-scoped storage to JSON and can write directly to disk. `browser.new_context(storage_state=...)` accepts that same JSON file on a later run, which is the correct cross-process replay primitive for bypassing the AEAT auth wall after a successful certificate-backed session has already been established.
- Playwright storage-state JSON should remain Playwright-native. AEAT-specific metadata such as certificate thumbprint, idle deadline, and prior handshake evidence should live in a separate sidecar file so the raw storage-state file stays consumable by Playwright tooling and easy to invalidate atomically.
- HTTPX cookie persistence is not a drop-in replacement for Playwright storage-state persistence. `httpx.Client.cookies` can be exported to a dict or reconstructed from a `Cookies`/`CookieJar`, but HTTPX does not expose one canonical on-disk session-state format that also preserves Playwright browser origins and local storage. The feature should therefore treat HTTPX cookie export/import as a secondary interoperability concern, not the authoritative persisted session artifact.
- The safest local persistence root is `settings.aeat_token_dir`, which already defaults to the gitignored `.tokens/` directory. The session files should stay under that root, be written atomically, and be restricted to user-only permissions on platforms where chmod semantics are available.

## Recommendation

- Standardize on `settings.aeat_token_dir / f"{settings.aeat_default_profile_name}-storage.json"` as the canonical persisted Playwright storage-state path.
- Persist AEAT metadata in an adjacent sidecar file that records at least: schema version, certificate thumbprint, certificate subject, certificate NIF, authenticated timestamp, idle deadline, the previous `HandshakeResult`, and a SHA-256 digest of the raw storage-state file.
- Validate a persisted session before reuse by checking: storage file exists, sidecar exists and parses, storage JSON has the expected Playwright shape, SHA-256 matches, idle deadline has not elapsed, and the current certificate thumbprint matches the thumbprint recorded in the sidecar.
- If any validation step fails, or if a resumed browser context fails `verify_login()`, delete both persisted files and fall back to a fresh certificate handshake plus fresh Playwright login.

---
tags:
  - "#adr"
  - "#session-persistence"
date: "2026-04-17"
modified: '2026-07-17'
related:
  - "[[2026-04-17-aeat-access-gate-adr]]"
  - '[[2026-07-16-protected-browser-certificate-auth-adr]]'
  - '[[2026-07-16-protected-browser-certificate-auth-research]]'
---

# `session-persistence` adr: `persist encrypted playwright storage_state with bound aeat metadata` | (**status:** `accepted`)

## Problem Statement

AEAT authentication is expensive enough to justify session reuse, but
Playwright storage state contains cookies and origin data that must never become
a plaintext cache file or cross an active-profile boundary. Resume must also
prove that persisted state still belongs to the selected provider identity and
still reaches that provider's authenticated resource.

## Decision

AEAT browser sessions are persisted only as encrypted, active-bucket-scoped
secure objects. `aeat_auth_session_storage_state_path(bucket_id, storage_stem)`
defines the logical object-key grammar, and application
`storage_state_paths()` selects the provider stem. The resulting `Path` value is
an object identity; it is never a filesystem destination and is independent of
the token-directory setting.

The outbound session adapter wraps the Playwright storage-state mapping and
provider metadata in one `PersistedBrowserSession`. It stores that envelope in
`AEAT_BROWSER_SESSION_NAMESPACE` through the active bucket's
`SecureObjectRepository`, using the namespace's `SESSION` sensitivity class and
current schema version. The repository encrypts the payload and digests the
logical object key at the storage boundary.

Browser state remains an in-memory mapping at the browser boundary.
`BrowserContext.storage_state()` returns the mapping captured after successful
authentication, and resume passes the validated mapping directly to
`BrowserSession.create_context(storage_state=...)`. The browser layer does not
discover, open, or preload a storage-state file.

Provider metadata is stored beside the state in the same encrypted envelope.
Its shared fields bind provider kind, authenticated identity, authentication
time, idle deadline, and a canonical storage-state hash. Certificate metadata
also binds certificate thumbprint and subject. Provider-specific metadata may
retain the authenticated landing or proof resource required by that provider.

## Validation and invalidation

Resume is opportunistic and fail-closed. A provider deletes or refuses the
encrypted record when its envelope, JSON shape, schema, storage-state hash,
provider kind, identity evidence, idle deadline, or provider-specific metadata
is missing or invalid. Certificate resume additionally requires the currently
selected certificate thumbprint and subject to match the persisted identity.

Local validation never substitutes for live proof. Certificate authentication
must navigate to the fixed protected resource defined by the protected-browser
decision and require a successful response at the exact final scheme, host, and
path. Cl@ve providers perform their own authenticated landing probe. Failed
resume state is removed before one fresh authentication attempt captures a new
encrypted envelope.

Former-product session keys and arbitrary caller-supplied filesystem paths are
not migrated, adopted, re-keyed, or treated as alternate session authorities.

## Rationale

One encrypted envelope keeps browser state and the metadata that validates it
under the same bucket route and repository transaction. A logical key preserves
stable provider identity without exposing cookies, origin storage, taxpayer
identity, or metadata in a filename. Passing only in-memory state to Playwright
also prevents a generic browser helper from becoming a second persistence path.

## Consequences

- Session reuse is partitioned by active bucket and provider.
- `SecureObjectRepository` is the only persistence writer for AEAT browser
  state; token-directory JSON, sidecars, atomic raw-file writers, and
  permission-based plaintext schemes are forbidden.
- Session tests exercise real encrypted repository round trips and real browser
  state mappings rather than mirrored persistence logic.
- Corrupt, stale, mismatched, or live-invalid state self-heals by deletion and
  one fresh authentication attempt.

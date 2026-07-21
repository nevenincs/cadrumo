---
tags:
  - "#adr"
  - "#protected-browser-certificate-auth"
date: '2026-07-16'
related:
  - '[[2026-07-16-protected-browser-certificate-auth-research]]'
modified: '2026-07-17'
---
# `protected-browser-certificate-auth` adr: `protected browser navigation is the sole certificate-session proof` | (**status:** `accepted`)

## Problem Statement

Certificate authentication previously carried a direct HTTPX handshake record
beside the Playwright navigation assertion. The direct path could not establish
browser authentication without unsafe plaintext key material, while its
backend selector, configurable probe, persisted result, and self-authored
context marker duplicated the only behavior that matters: whether a browser
context constructed with the selected PKCS#12 certificate can reach an
authenticated AEAT resource. Those retired surfaces are absent from current
code and remain described here only as the rejected architecture.

This decision makes protected browser navigation the single certificate-auth
proof. The retired handshake, backend, marker, verification-URL, and
persisted-handshake designs were deleted from the live and archived Vault
corpus. Their history remains available through git, but no resident document
can be interpreted as current authority.

## Considerations

- Playwright client certificates must be supplied when the browser context is
  constructed; post-construction certificate injection is impossible.
- The certificate must be scoped to the exact origin
  `https://www6.agenciatributaria.gob.es`.
- The sole protected proof resource is `/wlpl/TEWV-CORE/ResumenVlt`.
- A public Sede page, selector page, direct TLS response, context attribute, or
  persisted historical result does not prove that the current browser session
  is authenticated.
- Certificate credentials have one typed application boundary through
  `ActiveCertificateCredentials`.
- PKCS#12 passwords use `SecretStr` and are materialised only at two necessary
  credential-use boundaries: PKCS#12 decode and Playwright context
  construction.
- Certificate health, expiry, thumbprint, subject, and subject-derived NIF/NIE
  remain required identity evidence.
- Browser storage state and its metadata remain encrypted and integrity-bound.
- Certificate auth remains one implementation of the provider-agnostic
  `AuthProvider` contract.
- The browser session owns Chromium and must provide deterministic asynchronous
  teardown.
- This is a pre-release codebase. Retired persisted shapes and API surfaces are
  deleted, not migrated or tolerated.

## Considered options

- **Protected browser navigation only - chosen.** Uses the same real browser,
  certificate, cookies, origin, and protected resource that downstream reads
  require.
- **Direct handshake followed by browser navigation - rejected.** Duplicates
  network work, requires dead backend machinery, and makes a weaker preliminary
  signal part of the validity predicate.
- **Browser navigation plus a thumbprint marker - rejected.** The marker is
  written by the same code that later reads it and proves only
  self-consistency, not certificate presentation or AEAT acceptance.
- **Configurable origin or probe URL - rejected.** Permits public, selector,
  wrong-host, or unprotected targets to be represented as authentication proof.
- **Trust persisted historical proof without a live protected probe -
  rejected.** Cookies can expire or be invalidated independently of metadata
  integrity and idle time.
- **Retain retired backends and records for compatibility - rejected.** There
  are no released callers or durability requirements that justify carrying
  contradictory architecture.

## Constraints

The canonical protected URL is exactly
`https://www6.agenciatributaria.gob.es/wlpl/TEWV-CORE/ResumenVlt`. Certificate
origin binding uses the exact origin `https://www6.agenciatributaria.gob.es`;
the protected proof uses the exact path `/wlpl/TEWV-CORE/ResumenVlt`.

A successful proof requires Playwright navigation whose final URL retains that
exact scheme, host, and path and whose response is successful. Redirects to an
authentication selector, representation dispatcher, public Sede content,
another `www<N>` host, or any other path fail authentication.

Existing Cl@ve evidence reports that AEAT application hosts may rotate. This
decision deliberately does not introduce certificate-auth host fallback. If
the pinned certificate endpoint changes, authentication fails closed until new
live evidence and an architectural decision update the constant.

Fresh authentication and resume load the selected certificate, evaluate its
health, reject expiry, extract and validate its NIF/NIE, and bind the session
to its thumbprint and subject before protected navigation.

Encrypted persisted state validates the current schema, storage-state digest,
idle deadline, certificate thumbprint, certificate subject, and NIF/NIE before
use. No historical navigation or handshake record can satisfy the live proof.

No certificate password, PKCS#12 bytes, private key, browser cookies, storage
state, or sensitive identity material may enter logs, ordinary configuration
files, plaintext metadata, or CLI payloads.

Every browser session used by an auth provider declares `async close()`. An
auth provider owns only the session it constructs through its configured
`BrowserSessionFactory`; the production-unused per-call borrowed-session seam
is deleted. Optional or duck-typed teardown is forbidden.

## Implementation

Define one canonical certificate protected-resource constant composed from the
centrally owned exact origin and exact path. It is not an environment setting
or per-call override.

`AeatAuthenticator` remains the concrete certificate `AuthProvider`. It
receives `ActiveCertificateCredentials`, constructs `CertificateBundle`,
applies certificate health and expiry policy, and extracts the certificate
NIF/NIE. `CertificateBundle.password` remains `SecretStr`.

Certificate loading materialises the `SecretStr` only for the PKCS#12 decoder,
then retains the validated PKCS#12 bytes and certificate identity without
retaining a separate plaintext password value.

Certificate context provisioning contributes only the Playwright
`client_certificates` argument. Its `origin` is the canonical exact origin and
its `pfx` value is the immutable PKCS#12 byte sequence already loaded, parsed,
and fingerprinted into the selected `LoadedCertificate`. Playwright therefore
receives the same certificate identity that the session metadata records; it
must never re-read the credential path after validation. The `passphrase` is
materialised from `SecretStr` at the second and only other necessary boundary,
immediately before `browser.new_context(...)`; the materialised context
argument is discarded immediately after construction.

`BrowserContextProvisioner` remains the construction seam but loses context
annotation. Certificate context markers, marker validation, post-hoc preload
validation, and their compatibility tests are deleted.

Fresh authentication performs one authoritative sequence:

1. Load and validate the selected typed credentials and certificate identity.
2. Construct a browser context with the certificate bound to the canonical
   origin.
3. Navigate to the canonical protected URL.
4. Accept the session only when the response succeeds and the final origin and
   path exactly match the canonical protected resource.
5. Capture encrypted storage state and current certificate-bound metadata.

Resume validates the encrypted persisted-state schema, digest, idle deadline,
thumbprint, subject, and NIF/NIE, then constructs a new certificate-bound
context with that storage state and performs the same protected-resource
probe. Any validation or navigation failure deletes the persisted state and
attempts the single fresh-auth path. `verify()` uses the same protected probe;
there is no separate handshake verification path.

Certificate session, assertion, and persisted metadata retain provider kind,
certificate thumbprint, certificate subject, identity NIF/NIE, timestamps,
storage-state integrity, and protected-resource evidence. They do not contain
`HandshakeResult`, handshake-success flags, backend names, or marker evidence.

The retired handshake function and result, certificate-backend taxonomy, HTTPX
fallback, backend dispatch, backend and verification-URL settings, context
markers, annotation, and marker assertions must remain absent. The current
persisted certificate-session schema replaces the historical handshake-bearing
schema outright; older pre-release envelopes are refused and deleted.

`BrowserSessionLike` and `AuthProvider` declare mandatory `async close()`.
Providers directly await deterministic browser-session teardown while
preserving primary exceptions. The per-call `browser_session=` seam and every
`getattr(..., "close", None)` compatibility path are deleted.

Tests prove production behavior rather than reproduce the predicate. Context
construction is exercised through the production browser boundary,
persistence uses the encrypted production store, and the opt-in live
certificate test accepts success only at the canonical protected resource.

## Rationale

A direct handshake can show only that some TLS exchange occurred. It cannot
prove that the browser received the certificate, that AEAT established the
required authenticated cookies, or that the protected read surface is
available. The protected browser page proves those conditions through the same
mechanism downstream readers use.

Removing the handshake, backend, and marker stack eliminates a permanently
failing fallback, duplicated validity fields, self-authored evidence, unsafe
historical design, configurable false-positive targets, and persisted data that
does not contribute to trust.

The decision preserves the durable architecture: typed credential selection,
`SecretStr` handling, PKCS#12 loading, certificate health and identity
validation, encrypted storage, provider abstraction, browser-owned context
construction, and deterministic lifecycle ownership.

## Consequences

Certificate authentication has one proof predicate shared by fresh
authentication, resume, and verification. Maintainers no longer reconcile
browser results with handshake records, backend settings, or context markers.

The auth and persistence schemas become smaller. Existing pre-release
certificate sessions are invalidated and recreated rather than migrated.

Operators lose a standalone handshake diagnostic and configurable verification
target. Certificate diagnostics continue to report configuration, loading,
identity, and health; authenticated reachability is reported only by the real
protected-browser probe.

Authentication depends on the pinned `www6` protected endpoint. Host or route
drift causes a loud failure and requires new live grounding before the
architecture changes.

Browser-session implementations must implement asynchronous closure. This
strengthens resource ownership and removes silent Chromium-leak compatibility
behavior.

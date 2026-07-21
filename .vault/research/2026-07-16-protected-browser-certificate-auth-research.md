---
tags:
  - '#research'
  - '#protected-browser-certificate-auth'
date: '2026-07-16'
modified: '2026-07-17'
related:
  - '[[2026-04-17-aeat-access-gate-adr]]'
---

# `protected-browser-certificate-auth` research: `reconcile certificate proof with the real browser authority`

This research reconciles the certificate-auth ADR chain against the current
implementation and the protected AEAT resource that downstream live reads
actually require. It corrects the earlier conclusion that a direct handshake,
context marker, and navigation assertion formed a working layered proof.

## Sources

- Playwright Python browser API, `client_certificates` option:
  `https://playwright.dev/python/docs/api/class-browser`.
- Canonical AEAT authorities and paths:
  `src/cadrumo/core/external_constants.toml`, sections `aeat.domains` and
  `aeat.sede_paths`.
- Certificate loading, backend dispatch, and direct handshake:
  `certificate.py`, `_certificate_backends/_playwright_context.py`, and
  `_certificate_backends/_httpx_fallback.py`.
- Browser context construction and authentication:
  `CertificateContextProvisioner`, `AeatAuthenticator.authenticate`,
  `AeatAuthenticator.verify`, and `BrowserSession.create_context`.
- Persisted certificate evidence:
  `PersistedSessionMetadata`, `CertificateSessionDetail`, and
  `CertificateLoginAssertionDetail`.
- Governing decisions:
  `2026-04-17-aeat-access-gate-adr`,
  `2026-04-17-session-persistence-adr`,
  `2026-04-18-auth-provider-abstraction-adr`,
  `2026-04-18-auth-protocol-adr`,
  `2026-04-17-browser-leak-adr`, and
  `2026-06-04-live-auth-decomposition-adr`.

## Findings

### The direct handshake path cannot establish the claimed proof

The selected Playwright backend delegates standalone verification to the HTTPX
fallback. The fallback intentionally refuses to materialise plaintext PEM and
private-key files and therefore returns an unsuccessful `HandshakeResult`.
Fresh and resumed certificate authentication nevertheless require successful
handshake evidence. Production authentication is therefore blocked while tests
manufacture success through an injected handshake verifier.

A direct TLS response would remain insufficient even if it succeeded. It
cannot prove that the Playwright context received the certificate, that AEAT
issued the browser session cookies, or that the protected taxpayer resource is
available.

### The context marker is construction metadata, not authentication evidence

`CertificateContextProvisioner` writes a thumbprint attribute onto the context
and later code reads the same attribute. That confirms only that application
code annotated an object. It does not observe certificate presentation or AEAT
acceptance and must not contribute to the validity predicate.

### The current configured origin is not the protected authority

The configurable verification URL defaults to the public Sede origin. The
centrally recorded protected resource is the exact combination of
`https://www6.agenciatributaria.gob.es` and
`/wlpl/TEWV-CORE/ResumenVlt`. Playwright scopes client certificates by exact
origin, so the public Sede default cannot stand in for the protected `www6`
authority.

Other AEAT workflows show that `www<N>` hosts can change. Introducing fallback
would make the proof ambiguous. The safe response to endpoint drift is a loud
failure followed by new live evidence and a deliberate authority update.

### Certificate identity must be bound to the loaded bytes

Certificate loading reads, parses, and fingerprints one PKCS#12 byte sequence.
Passing its source path to Playwright would create a second file read after
validation: an operator or concurrent process could replace the file, causing
Playwright to present a different certificate from the identity recorded in the
session. The context provisioner must instead pass the retained private
`LoadedCertificate` PKCS#12 bytes through Playwright's in-memory `pfx` field.
That makes the parsed identity, recorded fingerprint, and browser-presented
credential one immutable input and removes the path replacement race.

### Persisted handshake evidence adds no trust

Persisted handshake fields record a historical result from the weaker proof
path. They cannot show that current cookies remain valid. Resume must validate
the encrypted state, certificate identity, integrity digest, and idle deadline,
then repeat the same protected browser navigation used for fresh
authentication.

The persisted schema is pre-release and may be replaced outright. A
handshake-bearing envelope should be refused and deleted, not migrated or read
through a compatibility branch.

### The durable architecture is narrower than the retired design

The following parts remain sound and should survive:

- one typed `ActiveCertificateCredentials` boundary;
- PKCS#12 loading with `SecretStr` materialisation only at the two necessary
  credential-use boundaries: PKCS#12 decode and Playwright context construction;
- certificate health, expiry, thumbprint, subject, and subject-derived NIF/NIE;
- the provider-agnostic `AuthProvider` abstraction;
- encrypted browser storage state and integrity metadata;
- Playwright `client_certificates` supplied at `new_context` time;
- browser-session ownership with mandatory asynchronous teardown.

Backend enumeration, the HTTPX fallback, direct handshake records, configurable
verification URLs, context markers, post-hoc preload validation, persisted
handshake fields, and optional teardown are contradictory or dead.

## Recommendation

Use one certificate implementation and one proof predicate. Pass the exact
PKCS#12 bytes already loaded, parsed, and fingerprinted through Playwright's
in-memory `pfx` field and bind them to the exact `www6` origin when constructing
the context. Navigate to the exact protected resource, and accept fresh,
resumed, or verified authentication only when the final URL and successful
response still identify that resource.

Delete every parallel backend, handshake, marker, compatibility, and persisted
legacy surface. Preserve the typed credential, certificate identity, encrypted
state, provider abstraction, and deterministic browser lifecycle contracts.

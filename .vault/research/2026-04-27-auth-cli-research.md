---
tags:
  - '#research'
  - '#auth-cli'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-18-auth-protocol-research]]"
  - "[[2026-04-18-aeat-auth-providers-research]]"
  - "[[2026-04-21-clave-portal-reference]]"
  - "[[2026-04-21-auth-cli-adr]]"
---



# `auth-cli` research: auth cli surface over pluggable auth providers

Kent needs a discoverable CLI entry point to manage AEAT authentication sessions.
Before issue #285, the `AuthProvider` protocol (landed in PRs #295 and #297) had no
user-facing surface: Kent could not list available providers, sign in, inspect session
TTL, or clear a persisted session from the command line. Every downstream sub-app
(status, submission, workflow) still relied on a stub provider because no top-level
command produced an authenticated `AeatSession` on demand.

## Evidence base

The following documents form the evidence base consolidated here:

- `2026-04-18-auth-protocol-research` — investigated the `AuthProvider` protocol
  design, the `AeatLoginAssertion` / `CertificateSessionDetail` Pydantic records, and
  the `AEAT_CERTIFICATE_THUMBPRINT_MARKER` context tag introduced by PR #295. Established
  that the protocol is the correct abstraction boundary for a CLI dispatch layer.

- `2026-04-18-aeat-auth-providers-research` — surveyed all four `AuthProviderKind`
  members (`certificate`, `clave_permanente`, `clave_movil`, `clave_pin`), their
  implementation status as of 2026-04-18, and the `select_provider` factory contract.
  Confirmed that only the certificate provider was production-ready for live reads at
  the time the CLI design was drafted.

- `2026-04-21-clave-portal-reference` — captured live Sede Electrónica browser
  observations that corrected three URL assumptions carried from earlier research:
  `SelectorAccesos.html` always returns 200, `/wlpl/` paths are only served on
  `www<N>.agenciatributaria.gob.es` (not `sede`), and Cl@ve Permanente is not offered
  by AEAT Sede today. Also confirmed that the Cl@ve Móvil flow is fully drivable via
  Playwright, enabling `ClaveMovilAuthProvider` to ship in the same PR.

## Consolidated finding

The research established that the correct CLI shape is a thin registry-centric dispatch
layer over the already-landed `AuthProvider` protocol and `AeatAuthenticator`. The
registry maps every `AuthProviderKind` to either a live provider or an "unavailable"
placeholder, giving Kent a single `aeat auth list-providers` view that teaches him what
is coming without pretending it works. Session persistence, TTL math, and logout file
operations all delegate to existing authenticator internals; the CLI adds no new auth
logic. The `2026-04-21-clave-portal-reference` live-portal observations were decisive:
they replaced stale URL assumptions and confirmed Cl@ve Móvil could ship immediately,
making the initial "all Cl@ve as placeholder" design obsolete before the ADR was merged.

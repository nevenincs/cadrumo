---
tags:
  - '#adr'
  - '#live-auth-decomposition'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-05-live-auth-decomposition-research]]'
  - '[[2026-06-04-repo-health-triage-research]]'
  - '[[2026-06-04-repo-health-triage-live-auth-split-invariants-audit]]'
  - '[[2026-05-19-live-iva-compensation-wallet-adr]]'
  - '[[2026-04-17-session-persistence-adr]]'
  - '[[2026-04-17-browser-leak-adr]]'
---

# `live-auth-decomposition` adr: `split live auth by custody boundary` | (**status:** `accepted`)

## Problem Statement

The live/auth surface is now one of the repo-health complexity hotspots. It mixes
operator auth readiness, active-profile identity checks, encrypted Playwright
session reuse, provider-specific browser automation, live-read orchestration,
diagnostic persistence, and CLI rendering across several large modules. This is
too much blast radius for unplanned refactoring, especially because live AEAT
access is legally sensitive and can bind observations to an active taxpayer
profile.

The decomposition must improve maintainability without changing live semantics:
no new auth provider, no broader live opt-in, no plaintext session files, no
provider logic in CLI handlers, and no weakening of the read-only AEAT posture.

## Considerations

The repo-health research recommends decomposing complexity hotspots only after
their invariants are known. The live/auth invariant audit identifies seven hard
rules: active-profile/provider identity must fail closed, live reads must enter
through the shared live gate, Playwright context construction owns certificate
and storage-state injection, encrypted storage state remains coupled to provider
metadata, primary exceptions must propagate, diagnostics must remain redacted and
profile-scoped, and authenticated AEAT reads must stay read-only.

Current code already has useful boundaries. `application/auth/_sessions.py` is
the central session-acquisition path. `application/auth/_operator.py` owns
operator-safe projections. `adapters/outbound/aeat/browser/session.py` owns
Playwright context construction. Auth provider modules own provider mechanics.
`application/live/__init__.py` owns live read/capture orchestration. CLI live
commands render preflight and result payloads.

## Constraints

No decomposition may bypass `AeatAccessGate.require_live_read()` or
`ensure_authenticated_aeat_session()`.

No decomposition may allow a Clave Movil provider identity mismatch to reach a
browser session, persisted-session probe, or live AEAT request.

No decomposition may move certificate passphrases, PKCS#12 handling, browser
cookies, storage state, raw diagnostic HTML, screenshots, or DNI/NIE values into
CLI payloads or plaintext filesystem artefacts.

No decomposition may add per-modelo, per-command, or per-live-surface auth
definitions. Auth is a generic cross-application capability and must remain
provider/profile/session based.

No implementation may silently swallow auth/browser exceptions. Cleanup failures
may be logged and suppressed only when a primary exception is already
propagating; primary failures must be raised through typed errors with the
original cause preserved.

## Implementation

Future implementation will split by custody boundary, not by command surface.

Application auth remains the sole owner of session acquisition, provider
selection, persisted-session probing, acquisition locking, active-profile
identity alignment, and operator-safe auth projections. Any extraction inside
`application/auth` must preserve the existing top-level package exports.

AEAT auth adapters remain the sole owners of provider-specific browser flows,
provider metadata schemas, provider diagnostics capture, and provider verification
mechanics. Shared helpers may be introduced for bounded teardown and encrypted
session metadata validation only when they reduce duplication without hiding
provider-specific failure modes.

The browser adapter remains the sole owner of Playwright context construction.
Certificate material and storage state are passed at `new_context()` time only;
post-hoc context mutation is not a valid architecture.

Application live remains the sole owner of live read/capture orchestration,
including the shared live-read gate, session acquisition call, Sede adapter call,
and persistence handoff. Sede adapters should drive remote reads with a verified
session, but must not acquire auth sessions themselves.

CLI live/config commands remain rendering and argument surfaces only. They may
call application projections and services, but must not import Playwright,
provider internals, certificate loaders, or secure session stores directly.

## Rationale

The custody-boundary split matches the existing dependency direction and keeps
sensitive material in the layers already responsible for it. Splitting by command
or by live product would duplicate auth rules across wallet, notifications,
expedientes, verify, censo, and future live surfaces, which would reintroduce the
same drift risk the audit is trying to prevent.

Keeping session acquisition in application auth also preserves a single place for
the active-profile identity guard. Keeping Playwright context construction in the
browser adapter preserves the certificate timing rule. Keeping CLI as rendering
only prevents operator-output work from gaining custody of secrets or remote
browser state.

## Consequences

The immediate implementation path is smaller and safer: extract cohesive modules
inside existing packages before moving public imports or changing behavior.

The main tradeoff is that some modules may remain large until their custody
subsections are separated in sequence. That is acceptable; correctness and audit
signals outrank a one-shot split.

Every implementation slice must carry regression evidence for identity mismatch
fail-closed behavior, persisted-session invalidation, Playwright certificate
construction, redacted CLI preflight, live-read gating, read-only remote actions,
and exception propagation.

## Codification candidates

- **Rule slug:** `live-auth-custody-boundaries`.
  **Rule:** Live AEAT auth decomposition must preserve application-auth session
  custody, browser-adapter Playwright context custody, provider-adapter mechanics
  custody, application-live orchestration custody, and CLI rendering-only
  custody.

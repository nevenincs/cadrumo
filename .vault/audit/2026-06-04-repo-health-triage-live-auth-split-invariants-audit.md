---
tags:
  - '#audit'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
  - '[[2026-06-04-full-repo-health-diagnostics-audit]]'
  - '[[2026-05-19-live-iva-compensation-wallet-adr]]'
  - '[[2026-04-17-session-persistence-adr]]'
  - '[[2026-04-17-browser-leak-adr]]'
---

# `repo-health-triage` Live/Auth Split Invariants Audit

Scope: W03.P11.S36, a pre-implementation audit for decomposing live AEAT/auth surfaces. No production code was changed by this step.

## Surfaces Audited

- `src/aeat/application/auth/_sessions.py`: central session acquisition, persisted-session probing, acquisition locking, and active-profile/provider identity fail-closed checks.
- `src/aeat/application/auth/_operator.py`: operator-safe auth configuration, status, test, and live preflight projections.
- `src/aeat/adapters/outbound/aeat/auth/_authenticator.py`: certificate-backed session record, persisted-state validation, invalidation, and browser-context marker checks.
- `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`: Clave Movil provider, encrypted session metadata, live browser flow, diagnostics, and teardown.
- `src/aeat/adapters/outbound/aeat/auth/_session_store.py`: encrypted browser-session persistence through the secure-object repository.
- `src/aeat/adapters/outbound/aeat/browser/session.py`: Playwright context construction, storage-state injection, certificate-provisioner kwargs, and retained-browser lifecycle.
- `src/aeat/adapters/outbound/aeat/auth/_certificate_backends/_playwright_context.py`: Playwright client-certificate construction and context-marker validation.
- `src/aeat/application/live/__init__.py` and `src/aeat/entrypoints/cli/_app_live.py`: shared live-read gate, session acquisition call sites, capture/read CLI preflight rendering, and live result surfaces.
- `src/aeat/domain/calculations/registry/_remote_state_guard.py`: authenticated-read policy vocabulary and AEAT write-action denylist used by remote-state surfaces.

## Invariants

### LIVEAUTH-INV-001 | active-profile identity must fail closed before remote auth

`ensure_authenticated_aeat_session()` and `require_verified_aeat_session()` call `_assert_active_profile_identity_matches_provider()` before reusing or acquiring a provider session. For Clave Movil, the active profile tax id and configured provider identity must both be present and equal. This is the safety rail that prevents a session for one taxpayer being reused under another active profile.

ADR consequence: the decomposition must keep identity matching in one application/auth boundary. CLI preflight may report mismatch details, but no CLI command or Sede adapter may independently decide that mismatch is acceptable.

### LIVEAUTH-INV-002 | live reads must enter through the shared live gate

Application live captures call `_active_verified_session()`, which loads settings, applies `AeatAccessGate.require_live_read()`, then delegates to `_ensure_authenticated_aeat_session()`. Under pytest the gate still requires live-test opt-in; operator runs continue through auth/profile/read-only guards.

ADR consequence: future module splits must not let Sede adapters, CLI commands, or direct Playwright helpers bypass `_active_verified_session()` or the central auth session service.

### LIVEAUTH-INV-003 | Playwright context construction owns certificate and storage-state injection

`BrowserSession.create_context()` accepts an auth `provisioner`, encrypted persisted `storage_state`, and an optional storage-state path. Certificate material is added to the Playwright `new_context()` kwargs only at construction time; `client_certificates` is popped after context creation. The Playwright certificate backend validates the context marker rather than trying post-hoc injection.

ADR consequence: browser/session decomposition must preserve a single construction-time boundary for client certificates and storage state. No later auth layer should mutate an existing context to add certificate material.

### LIVEAUTH-INV-004 | encrypted session state and provider metadata must remain coupled

`_session_store.py` persists Playwright storage state plus provider metadata as a SESSION-class secure object. Certificate and Clave Movil providers validate schema, provider kind, idle deadline, and storage-state hash before reuse. Invalid persisted state is deleted and converted into typed auth errors.

ADR consequence: fragmenting auth providers may split provider-specific metadata models, but storage-state persistence stays encrypted, profile-scoped, and invalidation-oriented. Raw Playwright storage-state files must not return as plaintext filesystem artefacts.

### LIVEAUTH-INV-005 | teardown may be best-effort, but exceptions must not disappear silently

Current auth/browser teardown has both fail-closed and best-effort paths. `BrowserSession.close()` raises a typed `BrowserError` on retained-browser close failure. Clave Movil context/session cleanup logs timeouts and close failures while re-raising the primary auth exception. The user mandate remains: do not swallow exceptions without a traceable, redacted log or typed boundary conversion.

ADR consequence: the split must classify teardown sites explicitly as primary-operation failures or secondary cleanup failures. Primary live/auth exceptions must propagate with `raise ... from exc`; cleanup suppression must be logged and redacted.

### LIVEAUTH-INV-006 | diagnostics are redacted and active-profile scoped

Auth diagnostics are persisted under the active bucket through secure-object repositories and projected as redacted summaries. Operator preflight reports only presence/status/alignment flags and redacted references, not raw DNI/NIE, certificate passphrases, cookies, or HTML.

ADR consequence: decomposition must keep raw diagnostic capture inside auth-adapter/application-auth custody and expose only projection models to CLI/live application surfaces.

### LIVEAUTH-INV-007 | authenticated AEAT reads stay read-only

The remote-state guard defines authenticated-read classifications and central AEAT write-action deny tokens. Clave Movil's auth browser policy restricts hosts and allowed auth browser actions. Live read/capture flows must not present, sign, pay, save, amend, upload, or otherwise mutate AEAT state.

ADR consequence: any extracted live surface must keep read-only policy checks close to the browser/network action, not only at command naming or CLI help text.

## Current Drift And Dependencies

- The working tree already contains concurrent edits in `_clave_movil.py`, `_authenticator.py`, and `_app_live.py` touching teardown timeouts, live-gate wording, portal host rendering, and payload construction comments. S37 must review those exact diffs before proposing code movement.
- `_session_store.py` compares storage-state hashes by ordinary string equality at provider call sites. Prior security audit material flagged constant-time comparison as a follow-up. Treat this as a tracked hardening edge, not as a prerequisite for the decomposition ADR unless code movement touches the comparison.
- `_authenticator.py` and `_clave_movil.py` both contain broad `except Exception` cleanup paths. Some are justified by Playwright's broad exception surface; S37 must decide which belong in a shared cleanup helper and which stay provider-specific.
- `application/live/__init__.py` remains a large mixed surface. The next split should preserve the top-level lazy export contract while separating session acquisition, capture orchestration, and persistence service access.
- `entrypoints/cli/_app_live.py` is a command-rendering module but still carries live preflight rendering and many payload row builders. It should consume application projections and avoid direct auth/browser imports.

## Required Regression Evidence For Implementation

- A real-behavior test proving Clave Movil active-profile/provider identity mismatch refuses before any provider acquisition or live browser request.
- Persisted-session reuse tests for malformed metadata, hash mismatch, expired state, and missing secure-object state, all fail-closed without plaintext storage files.
- Browser context tests proving `client_certificates` is passed at `new_context()` time, discarded from local kwargs after construction, and validated through the context marker.
- CLI/live tests proving preflight renders redacted presence/alignment fields and does not expose raw identity, certificate path secrets, passphrases, cookies, or HTML.
- Live gate tests proving pytest remote contact still requires explicit live opt-in while operator runs require auth/profile/read-only gates.
- Exception-path tests proving primary auth/browser failures propagate and cleanup failures are logged/redacted rather than silently swallowed.

## Verdict

Status: PASS for W03.P11.S36.

The audit found enough concrete invariants to write the dedicated S37 live-auth decomposition ADR. No production movement should start until that ADR states the owning modules for session acquisition, provider mechanics, browser context construction, live-read orchestration, diagnostics projection, and CLI rendering.

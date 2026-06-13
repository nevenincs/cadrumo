---
tags:
  - '#adr'
  - '#google-oauth'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - "[[2026-05-06-google-oauth-research]]"
  - "[[2026-05-06-google-oauth-audit]]"
  - "[[2026-05-06-secure-persistence-enforcement-adr]]"
---

# `google-oauth` adr: `Google OAuth authentication implementation` | (**status:** `accepted`)

## Problem Statement

The codebase has no working Google authentication. The forthcoming Google integration (Drive + Sheets read/write, mirrored bucket hierarchy, calculation visualisation, incoming-bucket ingestion) is gated on an authentication primitive that does not exist. ADR-0 defines that primitive: how the desktop app obtains, stores, refreshes, and revokes Google OAuth credentials per operator profile. The implementation plan replaces the post-teardown scaffold under `src/aeat/adapters/outbound/google/` in full; no shim, stub, or scaffold artifact survives ADR-0's execution.

This ADR is the foundation for ADRs 1-7 of the `google-oauth` series. Every subsequent ADR consumes the auth contract defined here; none of them re-decide it.

## Considerations

Decisions framed by:

- Codebase audit (`[[2026-05-06-google-oauth-audit]]`) — the discarded direction's footprint and stale entries.
- Forward research (`[[2026-05-06-google-oauth-research]]`) — 2026 OAuth practice, library versions, scope policy.
- Secure-persistence substrate (`[[2026-05-06-secure-persistence-enforcement-adr]]`) — landed encrypted SQL substrate with envelope encryption, OS-keychain master key, classification-aware records.
- Project profile model — single-operator Spanish autónomo desktop CLI with `AEAT_PROFILE` as the canonical identity axis.
- Project security charter (`#116`) — refuse-on-uncertainty stance for credential-bearing surfaces.

External references consulted: Google OAuth 2.0 for Desktop Apps, OOB and Loopback migration guides, RFC 9700 OAuth Security BCP, OWASP OAuth 2.0 Cheat Sheet, Google sensitive/restricted scope verification policy, PyPI release records for `google-auth`, `google-auth-oauthlib`, `google-api-python-client`.

## Constraints

- No `gcloud` runtime dependency. The teardown removed it; the rebuild does not reintroduce it.
- No plaintext credentials on disk. Sensitive-persistence policy refuses any plaintext OAuth token, refresh token, or client secret on the filesystem.
- No mocks in tests. Live integration tests gated by `AEAT_LIVE_TESTS_ENABLED`; unit tests use real `EphemeralMasterKeyProvider` + in-memory backends.
- Single canonical OAuth flow. Headless / device-grant / manual-paste fallbacks deferred.
- Single Google session per AEAT profile. No multi-Google-account-per-profile in v1.
- No verification dependency. The operator-supplied OAuth client operates in Cloud Console Testing mode against the operator's own project; no Google review process is required.
- `aeat auth` namespace is reserved for AEAT-side Sede authentication (cert / Cl@ve Móvil). Google authentication does not extend the AEAT auth provider registry.

## Implementation

### 1. Cloud Console application model — operator-supplied OAuth client

The operator creates their own Cloud Console project, enables Drive API + Sheets API, configures the OAuth consent screen in Testing mode with their own email as the sole test user, creates a Desktop application OAuth client, and downloads the JSON. The app imports the JSON via `aeat config google register --client-json <path> --profile <id>`. No Google verification process is required; sensitive scopes work for the operator's own account inside Testing mode.

The `oauth-client` record and `aeat config google register` CLI together form the abstraction over "where does the OAuth client JSON come from?" — v1 implements one source (operator import). A future hosted-distribution ADR may add an alternate source; that is a separate ADR amendment, not a stub in this build.

### 2. OAuth flow — Loopback IP + PKCE only

`google_auth_oauthlib.flow.InstalledAppFlow.from_client_config(client_config, scopes=SCOPES).run_local_server(port=0, open_browser=True, include_granted_scopes='true')`. The library binds an ephemeral local port on `127.0.0.1`, opens the system browser to the Google consent URL, and captures the authorisation code on redirect. PKCE is on by default in `google-auth-oauthlib >= 1.3.0`.

No device-authorisation-grant fallback. No manual-paste fallback. No headless mode. A workstation that cannot run a browser cannot authenticate in v1 — codified in §6 (Failure modes).

### 3. Library + version pins

```toml
"google-auth>=2.50.0",
"google-auth-oauthlib>=1.3.1",
"google-api-python-client>=2.195.0",
```

Explicitly not added (the codebase audit refuted the case for each):

- `google-auth-httplib2` — upstream archived 2026-03; transport is `requests` (already a transitive dep of `google-auth`).
- `gspread` — bus-factor-1 wrapper; `google-api-python-client` is used directly for Sheets v4.
- `google-cloud-functions`, `google-cloud-run`, `google-cloud-storage` — GCP product clients; the audit confirmed zero non-test callers.

Not added in v1 (deferred): `google-api-python-client` Docs API helpers (no consumer; audit refuted Docs round-trip).

### 4. Scope set v1

Two scopes requested at first login. Both are presented to the operator on the same consent screen.

```python
SCOPES_REQUIRED: tuple[str, ...] = (
    "https://www.googleapis.com/auth/drive.file",       # non-sensitive
    "https://www.googleapis.com/auth/spreadsheets",     # sensitive
)
```

`drive.file` is non-sensitive: it grants the app read+write only to files the app created or the operator explicitly opens via the Drive picker. No verification needed in any mode. Covers the outbound mirror (files the app creates), the workspace bucket (files the app creates and shares), and the inbound bucket (files the operator picks).

`spreadsheets` is sensitive but works in Testing mode for the operator's own account without verification (Cloud Console policy 2026). Covers ADR-6 (calculation → Sheets visual verification).

`documents` is excluded — no consumer. `drive` (full) and `drive.readonly` are restricted scopes requiring security assessment; both refused.

No incremental authorisation in v1. Re-running `aeat config google login` requests both scopes; no `--enable-sheets-export`-style opt-in flag.

### 5. Per-profile session model

Google sessions are 1:1 with AEAT profiles. The operator's active `AEAT_PROFILE` selects the Google session. Switching `AEAT_PROFILE=<id>` is the only mechanism to switch Google session.

SecureObjectRepository natural keys (HMAC-indexed, never stored plaintext):

```
aeat:google:profile:{profile_id}:oauth-client      # SECRET — operator-imported Desktop client JSON
aeat:google:profile:{profile_id}:oauth-token       # SECRET — refresh token
aeat:google:profile:{profile_id}:oauth-metadata    # AUDIT  — granted_scopes, account email, issued_at, last_refresh_at, reauth_required
```

No multi-Google-account-per-profile composite key. No global Google session shared across profiles. No `--account` flag. If a future operator workflow requires multiple Google accounts under one AEAT profile, that is a separate ADR amendment.

### 6. Token storage layer

All three records (oauth-client, oauth-token, oauth-metadata) live in `SecureObjectRepository` exclusively. No `keyring`-direct storage, no plaintext-on-disk fallback, no `env/.env`-resident credentials.

The substrate's existing layered model applies: master key resolves via `MasterKeyProvider` (auto/keyring/file/unsecured); each record is envelope-encrypted with a per-record DEK wrapped under the master key. The classification-aware refusal logic extends to Google records: when `aeat_secret_store_backend=unsecured` AND the active profile carries a real NIF/NIE/CIF, `aeat config google login` and `aeat config google register` refuse with a clear message directing the operator to a non-unsecured backend.

Access tokens are never persisted — held in memory only for the duration of one process invocation, refreshed lazily per §8.

### 7. CLI surface — `aeat config google` sub-tree

A new top-level `aeat config` sub-app is introduced for external-service configuration. Google sits under it. The `aeat auth` namespace remains reserved for AEAT-side Sede authentication (cert / Cl@ve Móvil); ADR-0 does not extend it.

```
aeat config google register --client-json <path> [--profile <id>]
aeat config google login    [--profile <id>] [--refresh-only]
aeat config google status   [--profile <id>] [--format json|text]
aeat config google logout   [--profile <id>]
```

- `register` reads the operator's downloaded Cloud Console JSON, validates its shape (`installed.client_id`, `installed.client_secret`, `installed.redirect_uris`), persists as `oauth-client` (SECRET-class). Re-running replaces. The original file is operator-deletable post-import.
- `login` reads the stored `oauth-client`, runs the loopback flow, persists the resulting refresh token as `oauth-token`, records `granted_scopes` and `account_email` in `oauth-metadata`. `--refresh-only` skips the consent flow and exercises an existing refresh token end-to-end (operator pre-warming before long batch operations).
- `status` reports: profile, account email, granted scopes, refresh-token issued-at, last-refresh-at, `reauth_required` flag, substrate readiness. Root `--format json|text` controls machine vs human rendering per the cli-workflow-redesign EPIC.
- `logout` deletes the `oauth-token` and `oauth-metadata` records. Does not remove the `oauth-client`. Re-`login` proceeds from the same client. To replace the OAuth client, operator re-runs `register`.

### 8. Refresh + revocation lifecycle

**Lazy refresh.** Before any Drive or Sheets API call, the auth layer checks `if expiry - now < 300 seconds: refresh()`. The 5-minute buffer covers clock skew and network latency. `google.auth.transport.requests.Request().refresh(creds)` mutates `creds` in place. The auth layer re-persists the refresh token after every refresh (Google rotates rarely but does rotate). `oauth-metadata.last_refresh_at` is updated.

**Pre-warm.** `aeat config google login --refresh-only` exercises the refresh path explicitly without browser flow. Useful before long batch operations (snapshot upload, bulk Sheets write).

**Revocation.** On `invalid_grant` (refresh token revoked at Google Account settings, or in Testing project after 7 days of inactivity, or after 6 months of unused inactivity for production tokens, or after the 100-token-per-account cap rotates the oldest token out): set `oauth-metadata.reauth_required = true`, raise `GoogleAuthRevokedError` with structured remediation, never auto-retry. The next `aeat config google` command refuses with the remediation message until `aeat config google login` runs and acquires a fresh refresh token.

**Testing-project warning.** On the first refresh after a `register`, the auth layer detects whether the OAuth consent screen is in Testing mode (heuristic: refresh token was issued <8 days ago AND the operator has not been warned). If so, log a one-time warning that Testing-mode refresh tokens expire 7 days after consent and the operator should re-`login` weekly or move the project to Production verification.

### 9. Failure-mode behaviour

Fail-loud across all auth failure modes. No degradation, no auto-retry on OAuth-protocol failures, no partial-functionality fallback. Every typed exception carries a structured remediation hint that the CLI renders prominently. Codified mapping:

| Failure mode | Exception | Remediation message |
|---|---|---|
| Network down during loopback flow | `GoogleAuthNetworkError` | Check connectivity, retry `aeat config google login` |
| Network down during refresh | `GoogleAuthNetworkError` | Check connectivity, retry the original command |
| OAuth client revoked at Cloud Console (`invalid_client`) | `GoogleAuthClientRevokedError` | Recreate Desktop client in Cloud Console; download JSON; `aeat config google register --client-json <path>` |
| Refresh token revoked (`invalid_grant`) | `GoogleAuthRevokedError` | `aeat config google login --profile <id>` |
| Refresh token expired (Testing-project 7-day cap) | `GoogleAuthExpiredError` | `aeat config google login --profile <id>` |
| `granted_scopes` missing a required scope | `GoogleScopeInsufficientError` | `aeat config google login --profile <id>` (re-consent acquires both scopes) |
| `aeat_secret_store_backend=unsecured` + real NIF | `UnsecuredModeRefusedError` | Set `AEAT_SECRET_STORE_BACKEND=auto` (or `file`/`keyring`); re-run command |
| Substrate keychain locked | `MasterKeyKeychainLockedError` | Unlock OS keychain; re-run command |
| Loopback port bind fails | `GoogleAuthLoopbackError` | Free port; restart workstation; if persistent, contact maintainers (no v1 fallback flow) |
| Browser fails to open | `GoogleAuthBrowserError` | Manually open the URL printed in the error; complete consent in browser |
| `oauth-client` not registered at `login` time | `GoogleAuthClientNotRegisteredError` | `aeat config google register --client-json <path>` |

Each `GoogleAuthError` subclass exposes `.remediation: GoogleAuthRemediation` with `command: str | None` and `why: str`. The CLI renders these in a dedicated boxed section after the error trace.

### 10. Out of scope (deferred)

- All Drive / Sheets / Docs API consumption — ADR-1 (provider abstraction), ADR-2 (bucket hierarchy + naming + atomicity), ADR-3 (snapshot + encryption boundary), ADR-4 (incoming buckets), ADR-6 (calculation → Sheets visualisation).
- Two-way edit reconciliation — ADR-7.
- Per-domain export taxonomy — ADR-5.

### 11. Scope clarifications

- This ADR governs Google OAuth tokens for the operator-supplied Cloud Console client.
- AEAT-side authentication (FNMT cert, Cl@ve Móvil → Sede browser session) remains under `application/auth/` and the existing AEAT auth registry. ADR-0 does not amend it.
- Substrate-level secrets (master key, recovery key, envelope DEKs) remain under `MasterKeyProvider` per the secure-persistence-enforcement ADR. ADR-0 does not amend it.

## Rationale

**Operator-supplied OAuth client.** A single-operator personal-tax tool gains nothing from Google's verification process at v1 scale. Verification is a 3-5 business day review for sensitive scopes (and weeks for restricted), creating dependency on Google's queue with zero functional benefit when the operator is the only user. The operator-supplied path operates entirely in Testing mode against the operator's own Cloud Console project — sensitive scopes work without any Google review.

**Loopback + PKCE only over device-grant fallback.** Device authorisation grant requires an OAuth client of TV/limited-input type, which the Desktop client cannot satisfy. Supporting device flow forces operators to create a *second* Cloud Console client. The audit found the use case is a single autónomo on a workstation with a browser — the targeted environment always has loopback. Failure modes for headless/locked-down environments fail loud per §9 rather than silently degrade.

**Both required scopes at first login over `--enable-sheets-export` opt-in.** Audit shows zero current Sheets consumers; the only future consumer is ADR-6 (calculation visualisation). Pre-granting `spreadsheets` removes a future re-consent UX bump and simplifies the CLI surface (no flag matrix). The privilege cost is bounded — `spreadsheets` is sensitive, not restricted, and operates entirely within the operator's own Cloud Console project.

**`aeat config google` namespace over `aeat google` top-level or `aeat auth --provider google`.** AEAT-side authentication and Google authentication are conceptually distinct: different threat models (AEAT session protects tax filings; Google tokens protect operator's Drive), different lifecycles (Sede session short-lived per browser; Google refresh token persistent), different recovery flows. Shoehorning Google into `aeat auth` confuses two domains. A new top-level `aeat config` sub-app frames Google as external-service configuration and leaves `aeat auth` clean.

**Per-AEAT-profile Google session over global or multi-account.** The codebase already has `AEAT_PROFILE` as the single identity axis. Audit found zero consumer for multi-Google-account flows. A 1:1 binding gives the operator a single mental model: "the AEAT profile I'm in determines everything."

**SecureObjectRepository over `keyring`-direct.** The substrate just landed with the explicit purpose of being the canonical secret-store. Diverging to `keyring`-direct introduces a parallel storage system with its own bootstrap, fallback, and revocation rules — directly contradicting the secure-persistence-enforcement ADR. Plaintext-on-disk is hard-refused by the existing sensitive-persistence policy test.

**Lazy refresh + fail-loud-on-revocation.** A daemon-based refresh-ahead pattern is architecturally inappropriate for a CLI tool (no daemon lifecycle to attach to). On-failure-only retry hides scope/quota/auth errors behind a generic 401 path. Lazy refresh is the simplest correct default; explicit `--refresh-only` adds an escape hatch for known long-running batch operations without changing the default behaviour.

**Fail-loud with structured remediation over best-effort degradation.** Tax-filing tools cannot afford silent state. Partial-functionality fallback couples auth concerns into every consumer's error handling. The structured remediation block lets operators recover without searching documentation — a small cost for a uniform failure UX.

## Consequences

**Positive.**

- Zero-Google-verification path for v1: no review queue, no privacy policy hosting, no support-email obligation.
- Single substrate for all operator secrets (Google tokens, AEAT cert passphrases, future provider tokens) — auditable, classification-aware, encryption-at-rest enforced.
- Per-AEAT-profile binding makes profile switching trivial; multi-profile operators (test/prod/business/personal) get cleanly separated Google sessions.
- Fail-loud + structured remediation gives operators concrete next-step commands rather than generic OAuth error traces.
- The `oauth-client` abstraction (substrate record + register CLI) admits a future alternate-source ADR amendment without architectural rewrite.

**Negative.**

- Operator one-time Cloud Console setup is ~10 manual clicks; not automatable. Each operator repeats this on each new workstation.
- No headless / locked-down workstation support in v1. Fails loud rather than degrading. Operators in such environments cannot use the integration.
- No multi-Google-account-per-profile. Operators with split personal/business Drive accounts must split their AEAT profiles to match.
- `register`-time validation of OAuth client JSON is best-effort; if Cloud Console issues a malformed JSON in some future change, the failure surfaces only at `login` time.
- Testing-mode 7-day refresh-token expiry forces weekly re-authentication if the operator stays in Cloud Console Testing status. Documented; surfaced via runtime warning; not blocked.

**Neutral.**

- The `aeat config` sub-app is new; introduces a top-level CLI namespace that other future external-service integrations (banking providers, LLM API keys, etc.) can also nest under.
- `oauth-client` JSON storage in the substrate creates a recovery dependency: losing the master key strands both AEAT cert passphrases and Google OAuth credentials. This is the same recovery surface the substrate already governs; ADR-0 inherits the recovery model rather than introducing a new one.
- The `aeat config google` namespace does not preclude future per-operator overrides via env var (e.g. `GOOGLE_OAUTH_CLIENT_JSON_PATH` for ephemeral CI runs); such overrides would be a v1.5+ amendment if a use case emerges.

## References

External:
- Google OAuth 2.0 for iOS and Desktop Apps — `https://developers.google.com/identity/protocols/oauth2/native-app`
- OOB Migration Guide — `https://developers.google.com/identity/protocols/oauth2/resources/oob-migration`
- Loopback IP Migration Guide — `https://developers.google.com/identity/protocols/oauth2/resources/loopback-migration`
- OAuth 2.0 Best Practices — `https://developers.google.com/identity/protocols/oauth2/resources/best-practices`
- OAuth 2.0 Scopes for Google APIs — `https://developers.google.com/identity/protocols/oauth2/scopes`
- Sensitive scope verification — `https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification`
- RFC 9700 OAuth 2.0 Security Best Current Practice — `https://datatracker.ietf.org/doc/rfc9700/`
- OWASP OAuth 2.0 Cheat Sheet — `https://cheatsheetseries.owasp.org/cheatsheets/OAuth2_Cheat_Sheet.html`
- `google-auth` PyPI — `https://pypi.org/project/google-auth/`
- `google-auth-oauthlib` PyPI — `https://pypi.org/project/google-auth-oauthlib/`
- `google-api-python-client` PyPI — `https://pypi.org/project/google-api-python-client/`

Internal:
- `[[2026-05-06-google-oauth-research]]` — codebase reality + 2026 OAuth grounding.
- `[[2026-05-06-google-oauth-audit]]` — pre-excision baseline.
- `[[2026-05-06-secure-persistence-enforcement-adr]]` — substrate contract this ADR consumes.

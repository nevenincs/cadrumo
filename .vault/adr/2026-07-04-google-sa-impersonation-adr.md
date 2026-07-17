---
tags:
  - '#adr'
  - '#google-sa-impersonation'
date: '2026-07-04'
modified: '2026-07-17'
related:
  - '[[2026-07-10-google-sa-impersonation-research]]'
---

# `google-sa-impersonation` adr: `Google service-account impersonation credential source` | (**status:** `accepted`)

## Problem Statement

GitHub issue #591 (Gap 5, follow-up to the earlier apoderado/#248 filing-detail work) asks
for a "SA-impersonation share UX": a gestor operating for several represented entities
wants one shared Google identity — a service account (SA) — to back the Google Sheets
export/calc-parity surface, instead of every team member running their own interactive
OAuth Desktop consent flow per profile. Scope clarification: this is Google Cloud
service-account impersonation for Application Default Credentials (ADC), the credential
source behind `adapters.outbound.google` (Sheets/Drive export mirror). It is unrelated to
AEAT apoderamiento (acting on behalf of a taxpayer before the Sede) or the certificate/
clave-móvil `application.auth` package — those are the AEAT portal identity; this ADR is
about the identity presented to the Google APIs when materialising the export mirror.

Today `adapters.outbound.google` has exactly one credential source:
`build_google_credentials` in `_factory.py`, which hydrates `google.oauth2.credentials.
Credentials` from the per-profile `OAuthClient` + `OAuthToken` records an operator
registers via the interactive `aeat config google register` / `login` flow
(`_oauth_flow.py`, `_session_store.py`). There is no ADC path and no impersonation path;
a shared-service scenario has no way to present a stable, auditable Google identity
without re-running the interactive consent flow on every machine.

## Considerations

- Google's supported pattern for "let a shared identity act without per-user interactive
  consent" is service-account impersonation: a human or CI identity authenticates via
  Application Default Credentials (ADC — `gcloud auth application-default login`, a
  workload identity, or an attached service account), and that identity is granted the
  IAM `roles/iam.serviceAccountTokenCreator` role on the target SA. `google-auth`'s
  `google.auth.default()` resolves ADC; `google.auth.impersonated_credentials.Credentials`
  wraps the resolved source credentials to mint short-lived, scoped tokens for the target
  SA (`target_principal`), optionally further scoped to a `subject` for Workspace
  domain-wide delegation (the issue's "domain-bound group" ask).
- `google-auth>=2.50.0` (already pinned in `pyproject.toml`) ships both `google.auth`
  (ADC discovery) and `google.auth.impersonated_credentials` out of the box — no new
  dependency.
- ADC freshness: `gcloud auth application-default login` issues a credential that expires
  or can go stale (revoked, wrong scopes, wrong project); the issue explicitly asks for
  auto-detection of staleness rather than an operator discovering it only when a Sheets
  call fails deep in the export path.
- Exact SA identity surfacing: an operator granting IAM roles on a target SA needs to see
  precisely which `service_account_email` string the app is about to impersonate before
  approving a role grant, not just "impersonation is configured."
- Safety: `sensitive-financial-data-secure-storage-only` and the project's secure-storage
  discipline apply to any persisted credential fields. Impersonated credentials are, by
  IAM design, better than the existing OAuth path on one axis — they hold no long-lived
  refresh token; the SA-impersonation flow re-derives a short-lived access token from ADC
  on every use — but the *source* ADC credential (or the operator's chosen ADC file) is
  itself sensitive and must never be logged or embedded in workflow state.
- `no-legacy-compatibility` / `composition-service-no-parallel-write-path`: SA
  impersonation must not fork a second Sheets/Drive write path. It is purely an
  alternative way to obtain a `Credentials`-shaped object; every downstream call
  (`apply_export_plan`, `GoogleDriveProvider`, the pull adapters) is unchanged.
- `aeat-schema-central-config`: the closed set of Google credential sources is a
  regulatory-adjacent but genuinely code-level taxonomy (not an AEAT registry value); it
  belongs as a `StrEnum` in `core`, per `aeat-architecture-boundaries`.
- `aeat-cli-pull-and-file-standard` and `aeat-locales-cli` govern the CLI verb and locale
  strings this ADR intentionally defers (see Constraints); the core credential-resolution
  slice does not touch either surface this wave.

## Considered options

- **Option A — SA impersonation as a first-class alternative `GoogleCredentialSourceKind`
  alongside the existing per-profile OAuth source, selected per profile.** Chosen. Keeps
  the existing interactive-OAuth path completely untouched for solo operators (the
  default), and adds impersonation as an explicit, typed, opt-in alternative for a gestor
  who has provisioned a target SA and granted the impersonating identity Token Creator.
- **Option B — Replace the OAuth path with SA impersonation as the only credential
  source.** Rejected: forces every solo operator (the common case) into IAM/GCP-project
  setup they do not need; breaks the zero-Cloud-Console-project-admin promise the
  interactive Desktop OAuth flow gives a non-technical taxpayer.
- **Option C — Model impersonation as a wrapper the CLI applies on top of whatever
  credentials `build_google_credentials` already returns (impersonate using the
  operator's own OAuth token as the source credential).** Rejected as the *sole* source:
  Google's own guidance is that impersonation's source credential should be ADC (a
  identity the impersonating principal controls independently of the AEAT profile's
  Google login), not the profile's own long-lived OAuth refresh token — chaining
  impersonation off a refresh token adds no isolation benefit and couples the two
  credential lifecycles. The per-profile OAuth token remains a valid *default* source
  identity for `google.auth.default()` to discover only when it happens to already be an
  ADC-shaped credential on the host; the typed model does not special-case this.
- **Option D — Land the CLI verb and locale strings in the same wave as the core
  resolver.** Rejected for this wave only (not a permanent decision): the executing wave
  is scoped to avoid touching the shared `locales/*.yml` files another campaign owns
  concurrently; CLI wiring is a documented, structurally scoped follow-up (see
  Constraints), not a re-litigation of whether a CLI surface should exist.

## Constraints

- `google-auth`'s ADC discovery (`google.auth.default()`) depends on environment
  discovery (`GOOGLE_APPLICATION_CREDENTIALS`, `gcloud` metadata, GCE/GKE/Cloud Run
  attached identity) that this application does not control and cannot mock
  meaningfully; a live IAM token-exchange call against a real, provisioned target SA
  is explicitly out of scope for this slice's tests (`aeat-safety-legal-gates` / no
  live external calls without an explicit opt-in) and is deferred to a live-gated
  integration test behind the project's existing `Settings.live_tests_google_enabled`
  (`AEAT_LIVE_TESTS_GOOGLE`) opt-in, which already gates the sibling OAuth-Desktop live
  tests (`test_oauth_live.py`) and needs no new settings field. The ADC-discovery
  *failure* path (no usable credential on host) is exercised for real in this slice by
  pointing `GOOGLE_APPLICATION_CREDENTIALS` at a nonexistent path — a genuine,
  hermetic, no-network reproduction of Google's own `DefaultCredentialsError`.
- CLI verb (`aeat config google ... impersonate ...` or a sibling of `google register`)
  and the four-language locale strings for it are explicitly deferred: the executing
  branch has a standing constraint this wave that the shared locale YAML files are owned
  by a concurrent campaign. The core resolver and its typed records are usable
  programmatically and by a future CLI slice without further core changes.
- ADC-freshness auto-detection (running `gcloud auth application-default login`
  automatically) is deferred: invoking `gcloud` as a subprocess is an operator-facing UX
  decision entangled with the CLI verb this wave defers; the core layer instead surfaces
  a typed, actionable refusal when ADC is stale/absent/wrong-scope so a future CLI layer
  can decide whether to auto-remediate or instruct the operator.
- Domain-wide delegation (`subject=`) requires a Google Workspace domain administrator to
  have granted the target SA domain-wide delegation for the requested scopes — a
  configuration this application cannot verify or provision; the resolver exposes the
  `subject` parameter typed and optional but does not attempt to detect delegation
  misconfiguration beyond the IAM error Google's own token endpoint returns.

## Implementation

A new `GoogleCredentialSourceKind` `StrEnum` (`oauth_desktop`, `service_account_
impersonation`) is added to `cadrumo.core` as the closed taxonomy for how
`adapters.outbound.google` may obtain a `Credentials`-shaped object, per
`aeat-architecture-boundaries`.

`adapters.outbound.google` gains a new `_impersonation.py` module (mirroring the
`_certificate_secret_backend.py` shape: typed records, a resolver function, a narrow
exception taxonomy) exposing:

- `GoogleImpersonationConfig` — a strict frozen pydantic record: `target_principal`
  (the SA email being impersonated), `target_scopes` (defaults to the existing
  `REQUIRED_SCOPES`'s data-access subset — `drive.file` + `spreadsheets`, not the
  identity scopes `openid`/`email`, which do not apply to a service-account grant),
  optional `delegates` (chained impersonation), optional `subject` (domain-wide
  delegation), and `lifetime_s` (bounded to Google's 3600s ceiling).
- `resolve_impersonated_credentials(config) -> Credentials` — resolves ADC via
  `google.auth.default(scopes=config.target_scopes)`, wraps the result in
  `google.auth.impersonated_credentials.Credentials(source_credentials=..., target_
  principal=config.target_principal, target_scopes=config.target_scopes, delegates=
  config.delegates, subject=config.subject, lifetime=config.lifetime_s)`, and returns it.
  The function eagerly calls `.refresh()` once (a real, but locally-mockable-via-real-
  ADC-fixture, network round-trip against Google's IAM credentials endpoint) so a
  misconfigured SA (missing Token Creator grant, wrong scopes, revoked delegation) fails
  loudly at resolution time rather than silently deep inside a later Sheets call.
- A typed error taxonomy under the existing `GoogleAuthError` base:
  `GoogleAuthAdcUnavailableError` (ADC discovery failed — no environment credential
  found), `GoogleAuthImpersonationRefusedError` (IAM refused the impersonation grant —
  the source identity lacks Token Creator on the target principal), each carrying
  `context={"target_principal": ...}` so a caller can render "grant roles/iam.
  serviceAccountTokenCreator to <source> on <target_principal>" without re-deriving it.
- `describe_impersonation_target(config) -> str` — returns the exact
  `target_principal` (satisfying the issue's "print the exact SA email" ask) without
  requiring a live token exchange, so a future CLI `show`/`status` verb can surface it
  before the operator grants IAM roles.

`build_google_credentials` (`adapters/outbound/storage/_factory.py`) is NOT changed in
this wave's core slice — it remains the OAuth-Desktop path. Wiring
`GoogleCredentialSourceKind` selection into the factory (reading a persisted per-profile
selection and dispatching to `resolve_impersonated_credentials` vs the existing OAuth
path) is the CLI-wave follow-up, once the storage/config surface for persisting a
`GoogleImpersonationConfig` per profile is decided alongside the CLI verb (a natural
non-secret candidate is the existing `GOOGLE_DRIVE_CONFIG_NAMESPACE`-shaped per-profile
secure-object pattern the OAuth records already use, sensitivity `FINANCIAL` for the
target principal / scopes, since no long-lived secret is stored — the impersonated token
is minted fresh on every use and never persisted).

## Rationale

Google's own security model treats impersonation as strictly additive to, never a
replacement for, interactive per-user OAuth: the source identity (ADC) still has to
authenticate independently, and IAM enforces the Token Creator grant server-side on every
token mint. Modelling it as a typed, opt-in alternative `GoogleCredentialSourceKind`
(Option A) preserves the existing default path byte-for-byte for the common solo-operator
case, and gives the shared-team case a credential source that never persists a long-lived
secret in this application's storage at all (the token is re-derived from ADC + IAM on
every use) — a stronger security posture than the OAuth-Desktop refresh-token path it sits
alongside, consistent with `sensitive-financial-data-secure-storage-only`. Scoping the
core resolver + typed records to this wave and deferring the CLI verb, locale strings, and
ADC-auto-remediation matches the executing constraint that the shared locale YAML files
are owned by a concurrent campaign this wave, and keeps the slice small enough to review
and land atomically without touching the config/CLI persistence layer decision, which
deserves its own review once the CLI shape is drafted.

## Consequences

- Gains: a gestor team can back the Sheets/Drive export mirror with one auditable SA
  identity instead of N interactive OAuth logins; the impersonated-token path never
  persists a long-lived credential, which is a net security improvement over the existing
  OAuth-Desktop refresh-token store for the teams that adopt it.
- The typed `GoogleImpersonationConfig` + resolver are usable today from application code
  or a test harness, but there is no operator-facing verb yet to configure or select this
  source; a CLI-less environment operator cannot yet opt in through the CLI, only
  programmatically. This is an explicit, tracked gap, not a silent one.
- ADC-freshness auto-detection and the `gcloud` re-login convenience the issue names
  remain open; the resolver surfaces a loud, typed refusal instead, which is safe but not
  yet as convenient as the issue's ideal UX.
- Because the resolver performs one real `.refresh()` call to validate the grant, a
  misconfigured or not-yet-provisioned SA is caught at resolution time — consistent with
  `no-silent-under-declaration`'s spirit applied to credential configuration: a broken
  impersonation grant must never silently fall through to an unauthenticated or
  wrong-identity Sheets write.
- Follow-up work (tracked against #591 remainder): the CLI verb family
  (`aeat config google credential-source ...` or similar, exact naming TBD at CLI-design
  time per `aeat-cli-pull-and-file-standard`), its locale strings across all four
  languages, per-profile persistence of `GoogleImpersonationConfig`, `_factory.py`
  dispatch wiring, and a live-gated integration test analogous to the certificate-source
  live probes.

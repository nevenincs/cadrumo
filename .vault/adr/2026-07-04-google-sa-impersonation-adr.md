---
tags:
  - '#adr'
  - '#google-sa-impersonation'
date: '2026-07-04'
modified: '2026-09-08'
body_hash: 'sha256:d8c40d6eae4a9c16975218d276aaef6551f95bdf1019870df85827a89bd9d982'
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
- `aeat-cli-pull-and-file-standard` and `aeat-locales-cli` govern the landed CLI verb and
  locale strings. The CLI reads the typed configuration directly and delegates credential
  resolution to the adapter rather than introducing another identity authority.

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
- The CLI verb and four-language locale strings were deferred from the original core
  slice because the shared locale catalogues were concurrently owned. They have since
  landed as `aeat config google credential-source set|show`; `show` renders
  `GoogleImpersonationConfig.target_principal` directly without a token exchange.
- ADC-freshness auto-detection (running `gcloud auth application-default login`
  automatically) remains deferred: invoking `gcloud` as a subprocess is an
  operator-facing UX decision. The core layer surfaces a typed, actionable refusal when
  ADC is stale, absent, or wrong-scope, so the existing CLI can later decide whether to
  auto-remediate or instruct the operator.
- Domain-wide delegation (`subject=`) requires a Google Workspace domain administrator to
  have granted the target SA domain-wide delegation for the requested scopes — a
  configuration this application cannot verify or provision; the resolver exposes the
  `subject` parameter typed and optional but does not attempt to detect delegation
  misconfiguration beyond the IAM error Google's own token endpoint returns.

## Implementation

A new `GoogleCredentialSourceKind` `StrEnum` (`oauth_desktop`, `service_account_`
`impersonation`) is added to `cadrumo.core` as the closed taxonomy for how
`adapters.outbound.google` may obtain a `Credentials`-shaped object, per
`aeat-architecture-boundaries`.

`adapters.outbound.google` exposes:

- `GoogleImpersonationConfig` — a strict frozen pydantic record whose canonical
  `target_principal` field is the SA email being impersonated. An operator-facing `show`
  or `status` surface reads this field directly when displaying the exact identity before
  an IAM grant; no parallel identity accessor is retained. The record also carries
  `target_scopes`, optional `delegates`, optional `subject`, and bounded `lifetime_s`.
- `resolve_impersonated_credentials(config) -> Credentials` — resolves ADC via
  `google.auth.default(scopes=config.target_scopes)`, wraps the result in
  `google.auth.impersonated_credentials.Credentials` using the typed configuration, and
  eagerly refreshes once so a misconfigured grant fails at resolution time.
- A typed error taxonomy under the existing `GoogleAuthError` base. Refusals carry
  `context={"target_principal": ...}` so callers can render the IAM remediation from the
  same canonical identity field without re-deriving it.

The credential-source selection remains an alternative to OAuth Desktop rather than a
parallel Sheets or Drive write path. Downstream export behavior consumes the resulting
`Credentials` object without knowing which source produced it.

## Rationale

Google's own security model treats impersonation as strictly additive to, never a
replacement for, interactive per-user OAuth: the source identity (ADC) still has to
authenticate independently, and IAM enforces the Token Creator grant server-side on every
token mint. Modelling it as a typed, opt-in alternative `GoogleCredentialSourceKind`
(Option A) preserves the existing default path byte-for-byte for the common solo-operator
case, and gives the shared-team case a credential source that never persists a long-lived
secret in this application's storage at all (the token is re-derived from ADC + IAM on
every use) — a stronger security posture than the OAuth-Desktop refresh-token path it sits
alongside, consistent with `sensitive-financial-data-secure-storage-only`. The original core slice
kept the resolver and typed records reviewable while the locale catalogues were
concurrently owned. The subsequently landed CLI, persistence, and factory dispatch reuse
those authorities: operator rendering reads `target_principal` directly, and runtime
resolution remains adapter-owned. ADC auto-remediation remains a separate UX decision.

## Consequences

- Gains: a gestor team can back the Sheets/Drive export mirror with one auditable SA
  identity instead of N interactive OAuth logins; the impersonated-token path never
  persists a long-lived credential, which is a net security improvement over the existing
  OAuth-Desktop refresh-token store for the teams that adopt it.
- The typed `GoogleImpersonationConfig` + resolver are selectable per profile through the
  landed credential-source CLI. Its `show` command reports the canonical target principal
  without ADC discovery or a token exchange.
- ADC-freshness auto-detection and the `gcloud` re-login convenience the issue names
  remain open; the resolver surfaces a loud, typed refusal instead, which is safe but not
  yet as convenient as the issue's ideal UX.
- Because the resolver performs one real `.refresh()` call to validate the grant, a
  misconfigured or not-yet-provisioned SA is caught at resolution time — consistent with
  `no-silent-under-declaration`'s spirit applied to credential configuration: a broken
  impersonation grant must never silently fall through to an unauthenticated or
  wrong-identity Sheets write.
- Remaining follow-up against #591 is limited to the optional operator-facing ADC
  auto-remediation decision. The CLI verb family, four-language locale strings,
  per-profile configuration persistence, factory dispatch, and live-gated integration
  probe are landed.

---
tags:
  - "#research"
  - "#cli-workflow-redesign"
date: 2026-05-12
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# CLI workflow redesign: config auth shape

## Summary

`aeat config auth` is the locked home for AEAT Sede authentication
configuration and session maintenance. It replaces the current
`aeat setup auth` surface without aliases, shims, compatibility routes, or
deprecation commands.

The target CLI root set is exactly:

- `aeat config`
- `aeat app`

No `aeat setup`, `aeat init`, `aeat archive`, top-level `aeat auth`, or
`aeat auth --provider google` command remains in the redesigned grammar.

`aeat config auth` owns AEAT Sede auth providers and sessions only. It does not
own Google OAuth, apoderamientos, representative identity selection, or live
AEAT submission.

## Live CLI facts

The current CLI root does not match the target contract. It mounts `init`,
`setup`, `config`, `archive`, `topic`, `help`, `app`, and `version` from
`cli/__init__.py:119` and `cli/__init__.py:249`.

`aeat config auth` is not currently mounted. The existing `aeat config` tree
exposes only `list`, `get`, `set`, `unset`, and `doctor` at `_config.py:103`.

The live auth CLI is under `aeat setup auth`. Its verbs are:

- `providers`
- `configure`
- `login`
- `status`
- `reset`
- `whoami`
- `logout`

Evidence: `_setup.py:190`.

`setup auth configure` writes `WorkflowState.auth` through `update_auth`. The
login, status, whoami, logout, and reset paths mutate readiness and session
markers. Evidence: `_setup.py:208` and `application/auth/_models.py:10`.

`setup auth` already uses `_emit`; `aeat config` often hand-rolls JSON output.
Evidence: `_setup.py:231`, `_common.py:44`, and `_config.py:127`.

## Implemented provider inventory

The implemented AEAT Sede auth providers are:

- `certificate`
- `clave_movil`

Both are present in `AuthProviderKind`, the application catalogue, the CLI
registry, and outbound `select_provider`.

Evidence:

- `application/auth/__init__.py:21`
- `_catalogue.py:33`
- `adapters/outbound/aeat/auth/__init__.py:134`

The following are reserved provider slots, but do not have auth provider
implementations:

- `clave_pin`
- `clave_permanente`
- `dnie_pkcs`

The portal registry knows Cl@ve PIN, Cl@ve Permanente, and DNIe as auth methods
or portal entry points, but they are not implemented auth providers. Evidence:
`domain/portals/_categories.py:47` and `portal_dnie_sede_entry.py:1`.

`apoderamiento` and representative identity selection are not part of the base
`config auth` grammar. They are reserved for a later apoderamientos ADR.

## Google OAuth placement

Google OAuth is not an AEAT Sede auth provider.

The existing Google OAuth ADR places Google configuration under
`aeat config google`, not under the AEAT auth provider registry. Evidence:
Google ADR lines 48, 121, and 187.

The current Google adapter is fail-closed inspection only and does not provide
a credentials backend. Evidence: `adapters/outbound/google/__init__.py:35`.

Therefore, the redesigned `aeat config auth` tree must not include:

- `google`
- `oauth_google`
- `aeat auth --provider google`
- `aeat config auth --provider google`

## Backend capability notes

The certificate backend supports:

- PKCS#12 loading
- health checks
- NIF extraction
- Playwright client-certificate context
- mTLS verification fallback

Evidence: `certificate.py:331` and `certificate.py:109`.

The Cl@ve Móvil backend supports:

- fresh login
- persisted-session probe and resume
- verification
- encrypted diagnostics
- QR and non-QR fallback
- separated session storage

Evidence: `_clave_movil.py:214`.

Apoderado support is not implemented. Cl@ve Móvil continues through
representation gates only when own-name access is already selected and refuses
representative identity selection. Evidence: `_clave_movil.py:1019`.

No bucket model or event backend exists in the current workflow state.
`WorkflowState` contains auth, profiles, active profile, declarations, and
review maps, but no `bucket_id` or event collection.

Live submission remains forbidden by backend gates, and the submission engine
exposes no transport method. `aeat config auth test` must therefore validate
authentication/session capability only; it must not submit to AEAT.

## Target command grammar

```text
aeat config auth providers [--format json|text]
aeat config auth configure --provider certificate|clave_movil|clave_pin|clave_permanente|dnie_pkcs [provider flags] [--format json|text]
aeat config auth status [--provider PROVIDER] [--format json|text]
aeat config auth test [--provider PROVIDER] [--format json|text]
aeat config auth clear [--provider PROVIDER|--all] [--sessions] [--locks] [--format json|text]
```

Every command must support `--format json` through `_emit`.

The `providers` command reports implemented providers and reserved slots
distinctly. `certificate` and `clave_movil` are implemented. `clave_pin`,
`clave_permanente`, and `dnie_pkcs` are reserved or unavailable until their
provider backends exist.

The `configure` command mutates provider configuration for the current bucket.
For unsupported reserved slots, the command must fail closed without writing
credentials or session state.

The `status` command reports configured provider and session state for the
current bucket.

The `test` command verifies auth/session readiness only. It must not perform
live AEAT submission.

The `clear` command clears configured provider state, sessions, and/or locks
for the current bucket, according to flags.

## Bucket and event requirements

Bucket/config mutations are bucket-scoped and emit structured events.

Required auth event names:

- `auth.provider.configured`
- `auth.provider.cleared`
- `auth.session.created`
- `auth.session.verified`
- `auth.session.cleared`
- `auth.lock.cleared`

Events are append-only, bucket-scoped, structured, versioned, and must not
contain secrets or raw credentials.

The current workflow state does not yet provide a bucket/event model, so
implementation must add or target the locked bucket and bucket-event
architecture rather than extending auth as unscoped global state.

## Removed surfaces

The redesign removes:

- `aeat setup auth`
- all `setup auth` verbs
- root `aeat setup`
- root `aeat init`
- root `aeat archive`
- top-level `aeat auth`
- `aeat auth --provider google`
- aliases
- shims
- compatibility routes
- deprecation routes

This is a hard migration, not a compatibility phase.

## Cross-references

Apex §3.3 requires `configure`, `status`, `providers`, `test`, and `clear`, and
identifies DNI-e, Google OAuth, and apoderamientos as placement-sensitive
slots.

The auth protocol abstraction anchors the provider/session split.

The historical Auth CLI ADR used top-level `aeat auth`; it is superseded for
placement by `aeat config auth` with no alias.

The Google OAuth ADR keeps Google under `aeat config google`, not AEAT Sede
auth.

The bucket and bucket-event ADRs lock the root command shape and event history
requirements.

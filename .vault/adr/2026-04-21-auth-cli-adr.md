---
tags:
  - "#adr"
  - "#auth-cli"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-18-auth-protocol-adr]]"
  - "[[2026-04-18-auth-provider-abstraction-adr]]"
  - "[[2026-04-12-cert-auth-adr]]"
  - "[[2026-04-17-aeat-access-gate-adr]]"
  - "[[2026-04-21-clave-portal-reference]]"
  - "[[2026-04-18-auth-protocol-research]]"
  - "[[2026-04-18-aeat-auth-providers-research]]"
  - "[[2026-04-27-auth-cli-research]]"
---

# `auth-cli` adr: `issue-285 aeat auth login / list-providers / status / logout` | (**status:** `accepted`)

## Supersession note (2026-05-21)

The top-level `aeat auth` command surface this ADR designed (`login` /
`list-providers` / `status` / `logout`) was retired by the later
accepted `2026-05-12-cli-workflow-redesign-config-auth-shape-adr`, which
states "Top-level `aeat auth` is not introduced" and places AEAT-Sede
authentication under `aeat config auth` (verbs `providers` /
`configure` / `status` / `test` / `clear`). The auth application and
domain layer this ADR mandated remains in force; only the CLI surface
shape is superseded. This ADR is therefore superseded-by-redesign at the
CLI-surface level.

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

Issue `#285` adds the first user-facing CLI surface over the pluggable
`AuthProvider` abstraction that landed in `#281` / `#282` and the
flattened provider layout that landed in #297. Kent — our Spanish
autónomo — needs a single, discoverable command group that lets him
list configured auth providers, sign in, inspect the live session
TTL, and clear a persisted session. Today the `AuthProvider` protocol
is wired through `AeatAuthenticator.select_provider` but there is no
CLI that exercises it. Every downstream sub-app (status, submission,
workflow) still leans on a stubbed `_StubAuthProvider` because there
is no top-level entry point that hands out an authenticated
`AeatSession` on demand.

## Considerations

- The CLI must target every provider kind in `AuthProviderKind` even
  though only the certificate provider is implemented today (via
  `AeatAuthenticator` behind `select_provider(...)`). The three Cl@ve
  kinds surface as "known, not configured" so that the table teaches
  Kent what is coming without pretending it works.
- `AuthProvider.describe()` is the only safe surface for loggable
  metadata — it already guards against leaking certificate bytes and
  fails soft (it returns an unavailable description instead of
  raising). The CLI MUST use `describe()` and MUST NOT call provider
  internals directly.
- Session persistence in `AeatAuthenticator` uses a single
  `{aeat_token_dir}/{profile}-storage.json` + `.meta.json` pair today.
  Multi-provider storage segmentation is a follow-up; this CLI must
  behave correctly against the current one-session-at-a-time file.
- `aeat auth status` must not itself reauthenticate — it reads the
  persisted metadata sidecar and renders its view against the
  authenticator's idle TTL math (`AEAT_SESSION_IDLE_TTL`). Reauth lives
  under `aeat auth login`.
- Env-var defaulting is mandatory per the issue. `AEAT_AUTH_PROVIDER`
  wins; otherwise the CLI picks the first configured provider in a
  deterministic order that leads with `certificate` (the only provider
  that is production-ready for live reads today).
- Output MUST be Kent-observable: the `list-providers` table labels and
  `status` language must be plain Spanish-friendly English without
  engineering jargon. Errors MUST be actionable and name the remedial
  env var or CLI command.
- `aeat doctor` already renders an auth-health line; this CLI must not
  duplicate that surface. Instead, `list-providers` is the authoritative
  per-provider view and `aeat doctor` remains the workstation-wide
  digest.

## Constraints

- The CLI MUST NOT introduce any new default-enabled live-write path.
  `aeat auth login` calls the existing `AeatAuthenticator.authenticate()`
  which still enforces the AEAT access gate and the certificate health
  gate.
- The CLI MUST remain unit-testable without a real browser. Provider
  dispatch, default resolution, table rendering, and logout file ops
  must all be exercised with `typer.testing.CliRunner` against pure
  fakes. `aeat auth login` against the real authenticator is exercised
  by follow-up `live_read` tests when Cl@ve lands.
- The CLI MUST NOT mutate `providers.json` or any vaultspec-managed
  state. Storage-state files are the only on-disk artifact it writes or
  removes.
- The CLI MUST honour the trilingual contract for any hard-coded
  user-facing strings. Command help is in English (code-default);
  dynamic runtime messages referencing provider state are English
  today; Spanish/Hungarian translations are deferred to the
  `Translatable` catalogue pass that covers the whole CLI.
- No mocks, patches, stubs, or fakes in live tests. The unit tests in
  this change-set use lightweight real objects — not `pytest_mock` or
  `unittest.mock`.

## Implementation

Create a new sub-app `src/aeat/entrypoints/cli/auth/` with this shape:

- `_registry.py` — maps every `AuthProviderKind` to either an
  implemented provider (delegating to :func:`aeat.adapters.outbound.aeat.auth.select_provider`)
  or an "unavailable" placeholder description. The registry is the
  single source of truth for provider ordering, default resolution,
  and list rendering. Other providers land by flipping
  `implemented=True` plus growing `select_provider`; the CLI requires
  no further changes.
- `_paths.py` — one helper that resolves the storage-state path pair
  for a given `(settings, kind)` tuple. For the current single-session
  authenticator, all kinds resolve to the same
  `{aeat_token_dir}/{profile}-storage.json` pair. When the follow-up
  multi-provider storage split lands, this helper is the only place to
  edit.
- `_render.py` — Rich-table and JSON emitters for the list-providers
  and status surfaces. Rendering is isolated from control flow so it is
  easy to unit-test.
- `_session.py` — reads the persisted metadata sidecar for status and
  logout. Uses Pydantic to validate the payload; bad sidecars fail
  closed with an actionable error (re-run `aeat auth login`).
- `__init__.py` — Typer sub-app exposing the four subcommands with
  help strings that lead with a Kent capability.

`aeat auth list-providers`:
- Default: every provider in the registry, columns `PROVIDER`,
  `STATUS`, `IDENTITY`, `EXPIRES`, `HEALTH`. The provider order is
  canonical (`certificate`, `clave_permanente`, `clave_movil`,
  `clave_pin`).
- `--configured`: filter to providers that `describe().configured` is
  True.
- `--all`: no-op today; reserved for future hidden providers (DNI-e,
  eIDAS).
- `--json`: emit a JSON array of `AuthProviderDescription` dumps plus
  the registry's `implemented` flag.

`aeat auth login --provider PROVIDER [--non-interactive] [--json]`:
- Resolves the provider via the registry. Unknown kinds → exit code 2.
- Not-implemented kinds (Cl@ve) → exit code 2 with the message
  "provider {kind} is known but not yet implemented; see EPIC #279".
- Builds the provider via :func:`aeat.adapters.outbound.aeat.auth.select_provider` and runs
  ``await provider.authenticate()``. The authenticator itself enforces
  the AEAT access gate and the cert-health proactive gate.
- `--non-interactive` short-circuits to an error when the provider's
  automation envelope is interactive (Cl@ve Móvil / Cl@ve PIN); for
  `certificate` and `clave_permanente` the flag is a no-op.
- On success prints a one-line confirmation plus the session TTL.
- `--json` emits a compact dump with `provider_kind`, `identity_nif`,
  `authenticated_at`, `idle_deadline`, `storage_state_path`.

`aeat auth status [--provider PROVIDER] [--json]`:
- Reads the persisted metadata sidecar via `_session.load()`.
- No file: exit 0 with "no active session; run `aeat auth login`."
- Fresh file: one-line "active provider: {kind} · authenticated {N}m
  ago · {M}m remaining before idle timeout · identity {NIF}".
- Expired (idle_deadline ≤ now): one-line "session expired {N}m ago;
  run `aeat auth login`" with exit code 0 (informational, not an
  error — the operator is just checking).
- `--provider` narrows the check to one kind; mismatched persisted kind
  returns a zero-exit "no active {kind} session" line.
- `--json` emits the full metadata dump plus derived TTL fields.

`aeat auth logout [--provider PROVIDER] [--all] [--json]`:
- Default: delete the storage-state + metadata pair for whichever
  provider is currently persisted; if nothing is persisted, a friendly
  no-op exits 0.
- `--provider PROVIDER`: delete only if the persisted session matches
  that kind. Mismatch is a zero-exit no-op.
- `--all`: delete every storage-state pair the registry knows about.
  Today this collapses to the single pair; the flag is future-proof.
- `--json` emits `{"removed_paths": [...]}`.

Default provider resolution in `_registry.default_kind(settings)`:
- If `settings.aeat_auth_provider` (env var `AEAT_AUTH_PROVIDER`) is set
  and valid → use it.
- Else iterate registry order and return the first kind whose
  `describe(settings).configured` is True.
- Else raise `NoConfiguredProviderError` which the CLI wraps in a
  `typer.BadParameter`.

Register the sub-app in `src/aeat/entrypoints/cli/__init__.py` alongside the existing
`status`, `submission`, etc. entries. Help string leads with the Kent
capability: "AEAT authentication provider management (#285)."

## Rationale

A thin `aeat auth` group is the smallest change that unblocks Kent's
"I just want to sign in" path while the broader Cl@ve providers are
still in flight. The registry-centric design gives us exactly one place
to grow when Cl@ve lands — every CLI subcommand reads from the same
registry — and keeps the four user-facing surfaces (list, login,
status, logout) lean and unit-testable. The CLI never reinvents auth
logic; it is a dispatch layer over the already-landed `AuthProvider`
protocol, `AeatAuthenticator`, and the `select_provider` factory.

## Consequences

- New module tree: `src/aeat/entrypoints/cli/auth/` with the four helpers plus
  tests colocated per `tests/README.md`.
- `src/aeat/entrypoints/cli/__init__.py` gains one `add_typer` call.
- `src/aeat/config.py` gains a new `aeat_auth_provider` Settings field
  so `AEAT_AUTH_PROVIDER` is declared in the one authoritative place
  and reflected in `.env.example` per the project mandates.
- `.env.example` grows a documented `AEAT_AUTH_PROVIDER=` line.
- Follow-up work: per-provider storage-state segmentation, Cl@ve
  providers, and `aeat doctor` parity with `list-providers` stay open
  under EPIC #279.
- No changes to submission, workflow, or status sub-apps; no drift
  against the live-write charter (#116) or export-first ADR.

## Addendum — live-portal discoveries (2026-04-21, post-implementation)

Three deltas emerged during the first driven browser session against
the real AEAT Sede Electrónica while finalising this PR. The `status:
accepted` decisions above remain valid; the addendum records what
changed between "ADR approved" and "merge-ready":

1. **Cl@ve Móvil ships in this PR.** The initial Considerations
   section describes a CLI that lists Cl@ve providers as "known, not
   configured". The live-portal capture made the Cl@ve Móvil flow
   fully drivable in Playwright, so `ClaveMovilAuthProvider` landed in
   the same PR instead of being deferred. The registry entry for
   Cl@ve Móvil is now `implemented=True`; Cl@ve Permanente is
   confirmed **not offered by AEAT Sede today** and remains a
   placeholder (see `2026-04-21-clave-portal-reference`
   § "Executive finding"). Cl@ve PIN stays P3 per the EPIC.

2. **Settings surface is larger than one field.** The "gains a new
   `aeat_auth_provider` Settings field" line in Consequences
   understates the actual change. The shipped Settings additions are:
   `aeat_auth_provider`, `aeat_clave_movil_dni_nie`,
   `aeat_clave_movil_dni_fecha`, `aeat_clave_movil_nie_soporte`,
   `aeat_clave_prefer_non_qr`, `aeat_clave_movil_timeout_ms`,
   `aeat_clave_sede_access_url_template`, `aeat_sede_expedientes_path`.
   All are documented in `env/.env.example` and guarded by
   `tests/test_config.py`.

3. **URL assumptions carried over from earlier ADR research are wrong.**
   `SelectorAccesos.html` is static HTML that always returns 200, and
   `/wlpl/<app>/<handler>` paths serve only on `www<N>.agenciatributaria.gob.es`
   (never on `sede`). These two assumptions are fixed for Cl@ve Móvil
   in this PR; they are latent in other modules (status reader,
   submission engine, justificante verifier) and tracked as
   follow-up GitHub issue #311 — see
   `2026-04-21-clave-portal-reference` § "Assumptions vs live-verified
   reality" for the canonical deltas. Any future AEAT URL decision
   must validate against that reference before landing in code.

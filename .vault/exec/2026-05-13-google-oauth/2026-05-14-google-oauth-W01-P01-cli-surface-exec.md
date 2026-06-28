---
tags:
  - '#exec'
  - '#google-oauth'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'S02+S04+S06+S07+S14'
related:
  - "[[2026-05-13-google-oauth-plan]]"
  - "[[2026-05-08-google-oauth-adr]]"
---

# `google-oauth` `W01.P01` CLI surface (S02+S04+S06+S07+S14 merged)

Five plan substeps merged into one cohesive deliverable per the user's no-placeholder mandate. The CLI surface lands together: backend session store, four Typer command bodies, sub-app registration, and 10 colocated CliRunner tests. After this commit, `aeat config google {register,login,status,logout}` resolves and operates against the OAuth backend committed in earlier P01 steps.

- Created: `src/aeat/adapters/outbound/google/_session_store.py` — encrypted SecureObjectRepository persistence for `oauth-client` (SECRET), `oauth-token` (SECRET), `oauth-metadata` (FINANCIAL); `delete_session` clears token+metadata, preserves client
- Created: `src/aeat/entrypoints/cli/_config/_google.py` — `google_app` Typer sub-app + `google_register`, `google_login`, `google_status`, `google_logout` commands + `_coerce_client_json` helper that unwraps the Cloud Console `{"installed": ...}` shape and normalises `redirect_uris` list → tuple before strict-mode validation
- Created: `src/aeat/entrypoints/cli/_config/test_google.py` — 10 CliRunner tests exercising every command with the session store stubbed via monkeypatch
- Modified: `src/aeat/entrypoints/cli/_config/__init__.py` — registered `google_app` via `app.add_typer(google_app, name="google")` after the existing profile/auth/bucket sub-apps
- Modified: `src/aeat/locales/{en,es,ca,hu}.yml` — added `cli.config.google.{help,register_help,login_help,logout_help,status_help,client_json_help,profile_help,refresh_only_help}` keys in all four supported locales
- Modified: `pyproject.toml` — added `_session_store.py` (S105 false positive on `_NAMESPACE_TOKEN`) and `test_google.py` (S105/S106/E501 false positives on synthetic OAuth fixtures) to `[tool.ruff.lint.per-file-ignores]`

## Description

`_session_store.py` mirrors the `aeat.outbound.aeat.auth._session_store` pattern: thin wrappers over `SecureObjectRepository().save / load / delete` keyed on the resolved AEAT profile name. Three namespaces:

- `aeat.google.oauth.client` (SECRET) — `OAuthClient.model_dump_json()`
- `aeat.google.oauth.token` (SECRET) — `OAuthToken.model_dump_json()`
- `aeat.google.oauth.metadata` (FINANCIAL) — `OAuthMetadata.model_dump_json()`

`delete_session(profile)` returns `(token_removed, metadata_removed)` and preserves the client so a subsequent `login` does not require re-importing the Cloud Console JSON.

`_google.py` orchestrates the four commands. Every command resolves the active profile via `resolve_active_profile(--profile)` and surfaces `GoogleAuthError` subclasses through `CliRefusedBoundaryError` so the project's standard exit-code + JSON envelope semantics fire.

- `register --client-json <path> [--profile]`: reads + parses the JSON, refuses non-Desktop shapes (`{"web": ...}`), refuses non-JSON or non-object payloads, normalises `redirect_uris` list → tuple, validates against `OAuthClient`, persists via `save_client`. Emits `operation\tconfig.google.register` + profile + client_id + project_id.
- `login [--profile] [--refresh-only]`: loads the stored client (raises `GoogleAuthClientNotRegisteredError` when absent), then either refreshes from existing metadata (when `--refresh-only`, raises `GoogleAuthExpiredError` when no prior login) OR runs `run_login_flow(client, profile)` and persists the resulting token+metadata.
- `status [--profile]`: reads client + metadata records, emits a structured payload covering `client_registered`, `session_present`, `account_email`, `granted_scopes`, `issued_at`, `last_refresh_at`, `reauth_required`. Honours the root `--format json|text` rendering flag.
- `logout [--profile]`: calls `delete_session`, reports which records were removed, asserts `client_preserved=True`.

Sub-app registration sits at the bottom of `_config/__init__.py` after the existing `profile`/`auth`/`bucket` add_typer calls, deferred-imported so the `_google.py` module's import chain (which pulls in the OAuth backend) does not load during basic `_config` introspection.

I18n keys added to all four locale catalogues (en/es/ca/hu) with idiomatic Spanish, Catalan, and Hungarian translations to maintain locale parity per the existing project test contract.

## Tests

- `pytest src/aeat/adapters/outbound/google/ src/aeat/entrypoints/cli/_config/test_google.py -q` — 65 passed (19 records + 9 profile_binding + 11 oauth_flow + 16 refresh + 10 CLI).
- `ruff check ...` — clean across the entire google package + new CLI surface.
- CLI test coverage: register persists, register refuses web shape, register refuses non-JSON, login refuses without client, login --refresh-only refuses without metadata, login --refresh-only returns existing summary, login runs consent via stubbed flow, status reports absence cleanly, status reports full session state, logout clears token+metadata + preserves client.

## Outstanding (final commits in P01)

- Live-gated tests (S15) — real Google OAuth + Drive API round-trips
- Forbidden-import test (S18) — guards against scaffold reintroduction
- Re-add `aeat.adapters.outbound.google` to `tests/import_contract/test_adr_layout_import_smoke.py`'s `ADR_LAYOUT_PACKAGES` and `CANONICAL_PUBLIC_SYMBOLS` against the new public surface

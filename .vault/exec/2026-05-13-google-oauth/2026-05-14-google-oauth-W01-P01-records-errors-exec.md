---
tags:
  - '#exec'
  - '#google-oauth'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'S03+S10+S11'
related:
  - "[[2026-05-13-google-oauth-plan]]"
  - "[[2026-05-08-google-oauth-adr]]"
---

# `google-oauth` `W01.P01` records + errors + registry (S03 + S10 + S11)

Three plan Steps merged into one cohesive deliverable per the user's no-placeholder mandate. Records, error hierarchy, and registry registrations land together — every error class binds at import, every record validates strictly, every public symbol re-exports through the package init.

- Created: `src/aeat/adapters/outbound/google/_records.py` — `OAuthClient`, `OAuthToken`, `OAuthMetadata`, `DriveAppProperties` pydantic records (frozen, strict, extra-forbid) + `DRIVE_FILE_SCOPE`, `SHEETS_SCOPE`, `REQUIRED_SCOPES` constants
- Created: `src/aeat/adapters/outbound/google/test_records.py` — 19 unit tests covering record validation, frozen contract, scope enforcement, error hierarchy unification, registry binding
- Created: `src/aeat/adapters/outbound/google/__init__.py` — public surface re-exports (replaced an inbound stub from a parallel agent that referenced non-existent class names; consolidated to my unprefixed naming convention which matches the existing `aeat.auth.AuthError` style)
- Modified: `src/aeat/core/errors/registry/_adapters.py` — appended 13 `GoogleAuthError` hierarchy registrations (`AUTH_GOOGLE`, `REFUSED_GOOGLE_VALIDATION`, `AUTH_GOOGLE_CLIENT_NOT_REGISTERED`, `AUTH_GOOGLE_CLIENT_REVOKED`, `AUTH_GOOGLE_REVOKED`, `AUTH_GOOGLE_EXPIRED`, `AUTH_GOOGLE_SCOPE_INSUFFICIENT`, `FAIL_GOOGLE_NETWORK`, `FAIL_GOOGLE_LOOPBACK_BIND`, `FAIL_GOOGLE_BROWSER_OPEN`, `REFUSED_GOOGLE_UNSECURED_MODE`, `LOCKED_GOOGLE_KEYCHAIN`, `REFUSED_GOOGLE_PROFILE_UNBOUND`)

Note: `_errors.py` (the typed `GoogleAuthError` hierarchy with 13 subclasses) was already on disk from earlier in this session and got picked up + committed by a parallel agent in `6083efbf` ("W09.P042 prep: canonical user_profile projection helpers + google/_errors fix"). The file content matches what I authored; this commit's registry rows are the consumers that bind the errors to stable codes.

## Description

Records: every model is `frozen=True, strict=True, extra="forbid"` per the project pydantic mandate. The `OAuthClient` record gates HTTPS-only on every URL field (`_https_only` validator). The `OAuthMetadata` record refuses any `granted_scopes` tuple that omits either Drive `drive.file` or Sheets `spreadsheets` (`_require_drive_and_sheets`), so a partial-grant consent flow cannot persist a metadata row that would silently break Sheets API calls. The `DriveAppProperties` record gates `revision >= 1` and defaults `schema_version="1"` so that the Drive `appProperties` commit-log payload is well-formed at construction time.

Error hierarchy: 12 leaf classes plus `GoogleAuthError` base, all subclasses of `AeatError` so the project-wide error taxonomy stays unified. `GoogleAuthValidationError` doubles as `ValueError` for pydantic compatibility. Each leaf binds to a distinct stable error code at import via the `__init_subclass__` hook in `AeatError`. Categories follow the existing taxonomy: `AUTH` for credential issues, `REFUSED` for policy refusals (validation, unsecured mode, missing profile), `FAIL` for transient network/IO failures, `LOCKED` for keychain unavailability.

The two `__init__.py` consolidation: a parallel agent left an `__init__.py` stub on disk that imported six classes (`GoogleAccountBinding`, `GoogleAuthSession`, `GoogleOAuthClient`, `GoogleOAuthClientSecret`, `GoogleOAuthToken`, `GoogleOAuthTokenResponse`) that did not exist anywhere in the codebase. Per the user's "remove duplications and consolidate everything, ensure everything is cohesively named" directive, I overwrote the stub with the actually-implementable public surface. The unprefixed naming (`OAuthClient`, not `GoogleOAuthClient`) mirrors the project's existing pattern (`aeat.auth.AuthError`, not `aeat.auth.AeatAuthError`) where the package name itself carries the disambiguator.

## Tests

- `pytest src/aeat/adapters/outbound/google/test_records.py -q` — 19 passed.
- `python -c "from aeat.adapters.outbound.google._errors import GoogleAuthError; print(GoogleAuthError.code.code)"` — prints `AUTH_GOOGLE`, confirming registry binding.
- The test file covers: every record's `frozen` + `extra="forbid"` + min-length contracts, the `OAuthClient` HTTPS validator, the `OAuthMetadata` scope enforcement, `DriveAppProperties` revision gating, the unified `GoogleAuthError` superclass relationship across all 12 leaves, the `GoogleAuthValidationError` ↔ `ValueError` dual inheritance, and the unique-stable-error-code contract across all 13 registered classes.

## Outstanding (deferred to subsequent commits)

The remaining P01 substeps still need to land: `_oauth_flow.py` (S05+S13), `_refresh.py` (S08+S09+S12), `_profile_binding.py` (S17), `_config/_google.py` (S04+S06+S07+S02), live-gated tests (S15), forbidden-import test (S18), Spanish CLI i18n strings (P08.S15-equivalent inside P01 scope), and re-adding `aeat.adapters.outbound.google` to `tests/import_contract/test_adr_layout_import_smoke.py`'s `ADR_LAYOUT_PACKAGES` + `CANONICAL_PUBLIC_SYMBOLS` against the new public surface. Each lands as its own cohesive commit per the no-placeholder rule.

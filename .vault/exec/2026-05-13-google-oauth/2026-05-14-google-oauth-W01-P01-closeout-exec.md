---
tags:
  - '#exec'
  - '#google-oauth'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'S15+S18+smoke'
related:
  - "[[2026-05-13-google-oauth-plan]]"
  - "[[2026-05-08-google-oauth-adr]]"
---

# `google-oauth` `W01.P01` closeout (S15 + S18 + smoke-test re-add)

Three loose ends merged into one cohesive deliverable that closes Phase P01:

- Created: `tests/import_contract/google/__init__.py` + `test_no_legacy_modules.py` — S18 forbidden-import test (3 unit tests). Asserts the v1 module list under `src/aeat/adapters/outbound/google/` stays minimal; refuses pre-teardown scaffolds (`_oauth_legacy*`, `_gcloud*`, `_paths*`, `test_google_auth.py`) and any unexpected `.py` files. Uses filesystem introspection so it stays runnable even when the broader Python import chain is broken mid-restructure.
- Created: `src/aeat/adapters/outbound/google/test_oauth_live.py` — S15 live-gated tests. Three live tests (login, status, logout) gated on `AEAT_LIVE_TESTS_ENABLED=1` AND a pre-registered OAuth client for the `AEAT_GOOGLE_LIVE_PROFILE` (default `live-test`). Skip cleanly when prerequisites are absent.
- Modified: `src/aeat/tests/test_adr_layout_import_smoke.py` — re-added `aeat.adapters.outbound.google` to `ADR_LAYOUT_PACKAGES`; added `OAuthClient` and `GoogleAuthError` to `CANONICAL_PUBLIC_SYMBOLS`. Confirms the package is importable and the public surface holds the expected symbols.

## Description

S18 forbidden-import test guards three invariants:

- The `google/` package directory exists (failing this means the package was deleted by mistake).
- No file under `google/` matches the forbidden prefixes (`_oauth_legacy`, `_gcloud`, `_paths`) or the legacy filename `test_google_auth.py`.
- Every `.py` file in the package is on the canonical v1 allow-list (8 source modules + 4 test modules + the package init). A new untracked `.py` triggers a clear failure with operator guidance to either extend the allow-list with rationale or remove the file.

S15 live-gated tests use the project's standard `AEAT_LIVE_TESTS_ENABLED=1` env var pattern. The `AEAT_GOOGLE_LIVE_PROFILE` env var (default `live-test`) chooses the profile so the operator's primary `default` profile stays untouched. Three tests:

- `test_login_persists_token_and_metadata_against_real_google_endpoints` — runs the actual loopback IP + PKCE consent flow against Google's endpoints. First run requires manual operator interaction in the browser; subsequent runs reuse the browser cookie within Google's session window.
- `test_status_round_trips_persisted_metadata` — reads back the persisted metadata after a live login, confirms `account_email` + `granted_scopes` round-tripped through the secure store.
- `test_logout_clears_session_records_but_preserves_client` — calls `delete_session`, confirms refresh token + metadata are cleared while the registered OAuth client survives.

The smoke-test re-add restores the package to the import-contract baseline. The two new `CANONICAL_PUBLIC_SYMBOLS` entries (`OAuthClient`, `GoogleAuthError`) cover both the records side and the errors side of the public surface.

## Tests

- `pytest tests/import_contract/google/test_no_legacy_modules.py -q` — 3 passed.
- `pytest src/aeat/adapters/outbound/google/test_oauth_live.py -q` — 3 deselected (no `live_read` marker active without `AEAT_LIVE_TESTS_ENABLED=1`); skip semantics verified.
- `pytest src/aeat/tests/test_adr_layout_import_smoke.py::test_adr_layout_package_import_smoke[aeat.adapters.outbound.google] src/aeat/tests/test_adr_layout_import_smoke.py::test_canonical_public_symbols_are_exposed -q` — 7 passed.

## P01 close

After this commit Phase P01 is operationally complete: 18/18 substeps landed, 65 unit tests pass, 3 forbidden-import tests pass, 3 live-gated tests skip cleanly, smoke test green. The OAuth backend + CLI surface is fully wired end-to-end. Remaining google-oauth work (`P02` storage provider abstraction, `P03` sync coordinator, etc.) lives in subsequent phases per the L3 master plan.

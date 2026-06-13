---
tags:
  - '#exec'
  - '#google-oauth'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'S08+S09+S12'
related:
  - "[[2026-05-13-google-oauth-plan]]"
  - "[[2026-05-08-google-oauth-adr]]"
---

# `google-oauth` `W01.P01.S08+S09+S12`

OAuth credential refresh lifecycle. Lazy refresh with 5-minute clock-skew buffer (S08), `invalid_grant` detection that flips `reauth_required=True` and never auto-retries (S09), and Testing-project 7-day cap warning fired once at the 6-day crossing (S12).

- Created: `src/aeat/adapters/outbound/google/_refresh.py` — `is_token_expired`, `detect_testing_project_warning`, `mark_reauth_required`, `refresh_credentials`, `utc_now` + 3 timedelta constants
- Created: `src/aeat/adapters/outbound/google/test_refresh.py` — 16 unit tests

## Description

Three constants pinned at module top:

- `ACCESS_TOKEN_REFRESH_BUFFER = 5 minutes` — matches `google.auth.credentials._helpers` so the local refresh trigger aligns with upstream's internal one.
- `TESTING_PROJECT_TOKEN_LIFETIME = 7 days` — Google's hard cap on Testing-project consent screens.
- `TESTING_PROJECT_WARN_AFTER = 6 days` — gives operators a 24-hour heads-up.

`is_token_expired(access_token_expiry, now, buffer)` — pure predicate. None expiry returns True (cold-start path). Inside the buffer returns True. At exactly expiry returns True. Used by callers (`_oauth_flow.run_login_flow` callers and the storage CRUD path) to decide whether to call `refresh_credentials`.

`detect_testing_project_warning(issued_at, now, last_refresh_at)` — returns the warning string only on the FIRST refresh that crosses the 6-day mark. Subsequent refreshes inside the same expired-window stay quiet (`last_refresh_at >= 6 days` past `issued_at` ⇒ already-warned ⇒ None). Past the 7-day cap entirely the warning is moot — caller should be raising `GoogleAuthExpiredError`.

`mark_reauth_required(metadata)` — frozen-model copy with `reauth_required=True`. Original metadata stays unmodified.

`refresh_credentials(*, client, token, metadata, now, refresher)` — orchestrator. Two early-exit cases:

- `metadata.reauth_required=True` ⇒ raises `GoogleAuthExpiredError` without calling the refresher; only `aeat config google login` can recover.
- Refresher raises `GoogleAuthRevokedError` (mapping of `invalid_grant`) ⇒ attaches `mark_reauth_required(metadata).model_dump(mode="json")` onto the exception's `context["metadata"]` so the caller can persist the flipped state before re-raising.

Otherwise: calls the refresher, builds `OAuthToken(refresh_token=new_refresh_token, token_uri=token.token_uri)` (the rotated refresh token Google may have issued), copies metadata with `last_refresh_at=now`, runs the warning detector, returns `(new_token, new_metadata, new_access_token, warning|None)`.

`OSError` from the refresher gets translated into `GoogleAuthNetworkError`; other `GoogleAuthError` subclasses pass through.

## Tests

- `pytest src/aeat/adapters/outbound/google/test_refresh.py -q` — 16 passed.
- `ruff check src/aeat/adapters/outbound/google/_refresh.py src/aeat/adapters/outbound/google/test_refresh.py` — clean.
- Coverage: constants match spec, expiry predicate edge cases (None / well-inside / inside-buffer / exact-expiry), warning detector (inside-window / first-crossing / quiet-after-crossing / past-7d), mark_reauth_required is a copy, refresh success rotates token + advances last_refresh_at, refresh emits warning at 6d crossing, invalid_grant attaches flipped metadata to exception, refresh refuses when already reauth_required, OSError translates to GoogleAuthNetworkError, other GoogleAuthError leaves pass through verbatim.

## Outstanding (subsequent commits)

- `_config/_google.py` (S04+S06+S07+S02) — CLI commands wired to login/refresh/status
- Live-gated tests (S15)
- Forbidden-import test (S18)
- Spanish CLI i18n strings
- Re-add `aeat.adapters.outbound.google` to import-contract smoke test

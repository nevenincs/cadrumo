---
tags: ['#exec', '#live-pull-verification-sweep']
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S09'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
---

# W02.P03.S09 - Focused Cl@ve live auth pytest lane

Scope: run the focused live auth pytest lane under explicit opt-in and prove skip/failure outcomes are not treated as green acceptance.

## Description

- Investigated the previous persisted-session pytest skip and traced it to the auth test package's pytest-isolated runtime, not to the Cl@ve provider or encrypted session store.
- Extended the full Cl@ve live test so a successful operator-mediated login also proves encrypted storage-state persistence and fresh-provider persisted-session probing in the same isolated runtime.
- Reran the Cl@ve live selector probe and full operator-auth Cl@ve test under explicit live opt-in.
- Ran a focused code review for the scoped test change.

## Outcome

The Cl@ve path for this row is verified. The full live test now performs the following real flow in one pytest-isolated root:

- `ClaveMovilAuthProvider.authenticate()` completes with operator-mediated Cl@ve approval.
- `verify()` confirms the fresh live session.
- The `clave-movil-storage` object exists in the encrypted session store.
- No plaintext storage-state or metadata file exists on disk.
- A fresh provider instance runs `probe_persisted_session()` through the central Playwright backend and receives a valid live assertion.

The earlier standalone persisted-session probe skip is now understood: each pytest case gets a fresh isolated runtime, so it cannot see a CLI-created session from `.tmp/...`. The acceptance proof therefore lives in the full-login test that creates and probes the session in the same runtime. Certificate live tests remain unclaimed because certificate credentials are not configured in the environment.

## Verification

- `AEAT_LIVE_TESTS_ENABLED=1 AEAT_CLAVE_MOVIL_FULL_LIVE_AUTH=1 AEAT_CLAVE_PREFER_NON_QR=true AEAT_BROWSER_HEADLESS=false uv run pytest src/aeat/adapters/outbound/aeat/auth/tests/test_clave_movil_live.py::test_clave_movil_provider_full_login_with_central_playwright_when_explicitly_enabled -m aeat_live -q -rs --tb=short` passed with 1 selected test.
- `AEAT_LIVE_TESTS_ENABLED=1 AEAT_BROWSER_HEADLESS=true uv run pytest src/aeat/adapters/outbound/aeat/auth/tests/test_clave_movil_live.py::test_clave_movil_playwright_entrypoint_reaches_live_selector -m aeat_live -q -rs --tb=short` passed with 1 selected test.
- `uv run ruff check src/aeat/adapters/outbound/aeat/auth/tests/test_clave_movil_live.py` passed.
- Code review was appended as `LPS-022` in `2026-06-12-live-pull-verification-sweep-code-review-audit`.

## Notes

The live run used the main worktree Cl@ve identity settings and a generated local `AEAT_SECRET_PASSPHRASE` for this process only. No raw taxpayer identity values, support numbers, passphrases, tokens, or storage-state payloads were written to this record.

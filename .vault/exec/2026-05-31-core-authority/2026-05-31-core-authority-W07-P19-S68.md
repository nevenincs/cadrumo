---
tags:
  - '#exec'
  - '#core-authority'
step_id: S68
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W07.P19.S68 - deduplicate SECRET_PASSPHRASE test constant

## Outcome

Created `src/aeat/adapters/outbound/aeat/auth/_test_fixtures.py` as the single declaration
site for `SECRET_PASSPHRASE = "correct-horse-battery-staple"`. Both `test_certificate.py`
and `test_authenticator.py` now import from `_test_fixtures` instead of redeclaring.
Added `conftest.py` in the same package with a session-scoped `secret_passphrase` fixture
wrapping the constant for future test use. RENAME-008.

W04/W05 lesson applied: both files were verified to use the same passphrase value for the
same test contract (PKCS#12 bundle generation/validation). Deduplication is safe.

## Commit

`823a41beb` — test(auth): W07.P19.S68

## Files touched

- `src/aeat/adapters/outbound/aeat/auth/_test_fixtures.py` — new, single SECRET_PASSPHRASE declaration
- `src/aeat/adapters/outbound/aeat/auth/conftest.py` — new, secret_passphrase fixture
- `src/aeat/adapters/outbound/aeat/auth/test_certificate.py` — removed inline constant, import from _test_fixtures
- `src/aeat/adapters/outbound/aeat/auth/test_authenticator.py` — removed inline constant, import from _test_fixtures

## Verification

62 passed (test_certificate.py 21 + test_authenticator.py 41 items).

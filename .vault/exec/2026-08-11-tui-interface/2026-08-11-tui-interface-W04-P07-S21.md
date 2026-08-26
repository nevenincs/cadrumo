---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:624f403728038a54e09eb20a3455a2e54314ef15f3a26caebb7daf15ce4414f0'
step_id: 'S21'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Prove exact operation binding expiry single use mismatch refusal cancellation cleanup and canary non-retention through real secret journeys

## Scope

- `src/cadrumo/entrypoints/tui/secret/tests/test_secret_journeys.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/secret/tests/__init__.py`
- `A` `src/cadrumo/entrypoints/tui/secret/tests/test_secret_journeys.py`
- `M` `src/cadrumo/entrypoints/tui/secret/tests/test_secret_journeys.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/secret/tests/test_secret_journeys.py -q -m integration` -> `pass` (9 passed)

## Notes

Scoped to PassphraseApp (the new build) plus the CredentialApp base it shares with Login/Registration: single-use dispatch, exact refusal binding, cancellation, and canary non-retention. Login and Registration already carry their own real-journey coverage (test_login_screen.py, test_registration_screen.py, test_registration_recovery_words.py, test_registration_language_switch.py); this file does not duplicate that.

Added a parametrized real-geometry proof (narrow/medium/wide) asserting every field and button has a positive, in-viewport region -- direct follow-up to the SourceActionCard height defect found during the S17-S19 relocation, per operator direction that presence and focus assertions alone had already been shown insufficient.

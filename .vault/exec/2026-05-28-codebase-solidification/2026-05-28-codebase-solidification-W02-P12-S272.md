---
step_id: S272
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W02.P12.S272-S281 — A3 auth-locale survivor cluster

## Scope

Ten Steps closed in one execution session: S272-S275 thread `translated_message=`
on `AeatLoginAssertionError` raises in `_clave_movil.py`; S276 adds real-behavior
tests for Clave Movil; S277-S280 thread `translated_message=` on raises in
`_authenticator.py`; S281 adds real-behavior tests for the authenticator.

## Outcome

### S272 — no_persisted_session (clave_movil)
Two raise sites in `_clave_movil.py` (probe_persisted_session guard at line 380,
_load_persisted at line 864) now carry
`translated_message="adapters.auth.clave_movil.errors.no_persisted_session"`.

### S273 — session_expired (clave_movil)
Two raise sites in `_clave_movil.py` (probe_persisted_session idle_deadline guard at
line 385, _resume_locked idle_deadline guard at line 1049) now carry
`translated_message="adapters.auth.clave_movil.errors.session_expired"`.

### S274 — storage_state_hash_mismatch (clave_movil)
Raise site in `_clave_movil.py` _resume_locked at line 1052 now carries
`translated_message="adapters.auth.clave_movil.errors.storage_state_hash_mismatch"`.

### S275 — page_missing_click (clave_movil)
Raise site in `_clave_movil.py` _click_clave_movil_button at line 1144 now carries
`translated_message="adapters.auth.clave_movil.errors.page_missing_click"`.

### S276 — test_clave_movil_translated_message.py
New file with 9 real-behavior tests:
- S276-A: _load_persisted carries no_persisted_session translated_message
- S276-B: probe_persisted_session carries no_persisted_session translated_message
- S276-C: probe_persisted_session carries session_expired translated_message on expired session
- S276-D: _resume_locked carries storage_state_hash_mismatch translated_message on hash mismatch
- S276-E: _click_clave_movil_button carries page_missing_click translated_message
- S276-F (x4 parametrized): all 4 locale keys resolve to non-placeholder copy
All 9 pass.

### S277 — already_active (authenticator)
Raise site in `_authenticator.py` authenticate() at line 496 now carries
`translated_message="adapters.auth.authenticator.errors.already_active"`.

### S278 — assertion_failed (authenticator)
Raise site in `_authenticator.py` authenticate() at line 573 now carries
`translated_message="adapters.auth.authenticator.errors.assertion_failed"`.

### S279 — resume_failed (authenticator)
Raise site in `_authenticator.py` _resume_from_storage_state() at line 1083 now carries
`translated_message="adapters.auth.authenticator.errors.resume_failed"`.

### S280 — metadata_parse_failed (authenticator)
Raise site in `_authenticator.py` _read_persisted_metadata() at line 1157 now carries
`translated_message="adapters.auth.authenticator.errors.metadata_parse_failed"`.

### S281 — test_authenticator_translated_message.py
New file with 8 real-behavior tests:
- S281-A: authenticate raises with already_active key when active session exists
- S281-B: authenticate raises with assertion_failed key on failed handshake probe
- S281-C: AeatLoginAssertionError carries resume_failed key (defensive-guard structural test)
- S281-D: AeatLoginAssertionError carries metadata_parse_failed key (defensive-guard structural test)
- S281-E (x4 parametrized): all 4 locale keys resolve to non-placeholder copy
All 8 pass.

## Locale keys

Scaffold + set for en/es/ca/hu (8 keys):
- `adapters.auth.clave_movil.errors.no_persisted_session`
- `adapters.auth.clave_movil.errors.session_expired`
- `adapters.auth.clave_movil.errors.storage_state_hash_mismatch`
- `adapters.auth.clave_movil.errors.page_missing_click`
- `adapters.auth.authenticator.errors.already_active`
- `adapters.auth.authenticator.errors.assertion_failed`
- `adapters.auth.authenticator.errors.resume_failed`
- `adapters.auth.authenticator.errors.metadata_parse_failed`

`python -m aeat.locales audit` returns `ok` for all four locales.

Note: locale file changes were included in the prior commit (22904f4b5, S282-S291 campaign)
because that campaign ran scaffold after this campaign's set operations.

## Files touched

- `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`
- `src/aeat/adapters/outbound/aeat/auth/_authenticator.py`
- `src/aeat/adapters/outbound/aeat/auth/test_clave_movil_translated_message.py` (new)
- `src/aeat/adapters/outbound/aeat/auth/test_authenticator_translated_message.py` (new)
- `.vault/plan/2026-05-28-codebase-solidification-plan.md`

## Test outcome

`pytest src/aeat/adapters/outbound/aeat/auth/` (excluding live tests) — 138 passed, 0 failed.

## Collision signal

`git diff -- src/aeat/adapters/outbound/aeat/auth/ src/aeat/locales/` before edits: no output (clean).

## Commit SHA

2ae01e779

---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S06-S07'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# W03.P03.S06-S07 - censo calendar hardening and live verification attempt

## Description

- Re-baselined the moved censo/calendar backend after shared-worktree drift.
- Ran `vaultspec-rag search --timeout 30`, `--timeout 180`, and finally `--timeout 300`; the final higher-timeout query succeeded after the indexer delay.
- Hardened `config profile censo apply` so it re-reads the persisted profile after censo apply and emits the same overview-engine calendar readiness summary used by `app overview calendar`.
- Hardened overview calendar filing evidence so `aeat_live_capture` external evidence is treated as justificante-verified, matching the calculation clean-state gate.
- Added W04 plan tracking for the current encrypted-store unlock blocker and final profile-bound live proof.

## Outcome

- `config profile censo apply` now reports `taxpayer_model_declared`, calendar range, obligation count, obligation modelos, warning codes, and defaulted modelos in both text and JSON payloads.
- Calendar evidence now distinguishes local ready-to-file rows from AEAT-submitted rows and marks live-captured AEAT justificante evidence as `justificante_verified = true`.
- Live network/browser reachability was verified with `test_clave_movil_playwright_entrypoint_reaches_live_selector`: passed.
- Profile-bound live reads could not be completed because the active encrypted secret store prompted for `AEAT_SECRET_PASSPHRASE`; this shell has no non-interactive passphrase and the OS keychain backend was unavailable.
- With `AEAT_LIVE_TESTS_ENABLED=1`, declaration and IVA live tests selected correctly but skipped or failed at the same active-bucket/secret-store boundary.

## Verification

- `ruff check` passed on touched calendar/censo files.
- `pytest src/aeat/application/overview/tests/test_calendar.py src/aeat/application/user_profile/tests/test_censo_sync.py src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py -q`: 63 passed, 11 deselected.
- `pytest src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -m hex_entrypoint -q`: 19 passed.
- `pytest src/aeat/application/overview/tests/test_calendar_taxpayer_model.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py -q`: 23 passed.
- `pytest src/aeat/core/errors/tests/test_registry.py src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py -m "unit or hex_entrypoint" -q`: 21 passed.
- `pytest src/aeat/adapters/outbound/aeat/auth/tests/test_clave_movil_live.py::test_clave_movil_playwright_entrypoint_reaches_live_selector -m aeat_live -q -rs`: 1 passed.
- `pytest src/aeat/adapters/outbound/aeat/sede/tests/test_declarations_live.py src/aeat/adapters/outbound/aeat/sede/tests/test_iva_compensation_wallet_live.py src/aeat/application/live/tests/test_iva_wallet_live.py -m aeat_live -q -rs` with `AEAT_LIVE_TESTS_ENABLED=1`: two skipped for no active bucket session; two failed on secret-store passphrase prompt.

## Open

- S06 and S07 remain open because no live Modelo 036/G313 snapshot was pulled/applied against the active profile during this run.
- W04 tracks the exact remaining requirement: unlock profile-bound storage non-interactively, rerun censo pull/compare/apply and live filing/message/justificante pulls, then prove legal obligation rows carry live submitted and justificante-verified evidence.

---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S08'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
  - '[[2026-06-12-live-pull-verification-sweep-live-auth-blocker-audit]]'
---

# W02.P03.S08 / W02.P04.S10-S13 / W03.P06.S27 - live authenticated read sweep

## Description

- Loaded the operator live Cl@ve Móvil settings from the local environment file without printing raw identity or support-number values.
- Created a fresh isolated encrypted profile root for the live exercise and used a process-local passphrase only for that profile store.
- Created a real active profile with the Cl@ve identity as profile tax id, configured `clave_movil`, and acquired a fresh Cl@ve Móvil session with the operator present.
- Re-ran authenticated read surfaces against the same isolated profile root: censo pull/compare, filed history, expedientes, notifications, justificante list, and overview calendar projection.
- Verified the CLI verb drift requirement during the same sweep: bulk filed history is attempted through `app live filed list` / `app live filed pull` options, not through a `pull-all` command.

## Outcome

Fresh Cl@ve Móvil session acquisition succeeded. `config auth login --provider clave_movil --fresh --reset-lock` returned `authenticated=true`, `fresh=true`, and `reused_persisted_session=false`; follow-up auth status reported `configured=true`, `authenticated=true`, `identity_alignment=matches`, and a live persisted session.

Authenticated read outcomes:

- Censo / Modelo 036 pull reached AEAT but refused with `AEAT sede G313 returned no readable censo for profile`; no censo snapshot was persisted, and `censo compare` correctly refused because no snapshot exists.
- Filed Modelo 303 history for 2026 succeeded with `row_count=0`; the matching pull succeeded with `captured_count=0`, `failed_count=0`, `justificante_metadata_count=0`, and `filing_evidence_stamped_count=0`.
- Expedientes Modelo 303 for 2026 succeeded with a persisted snapshot and `declaration_count=0`.
- Notifications pull succeeded with a persisted snapshot and `row_count=1`.
- Justificante list succeeded with `count=0`; no justificante pull was attempted because the authenticated filed-history probe returned no filed declaration row to target.
- Overview calendar for 2026 succeeded and projected both required Modelo deadline entries and the pulled AEAT notification as a `message` event with source `aeat_sede_notifications`.
- All-model filed history for 2026 was attempted through the `pull`/bulk-option surface and timed out after 180 seconds while still in authenticated preflight; the process was killed and no leftover all-model filed-list process remained.

## Verification

- `uv run aeat --format json config auth configure --provider clave_movil` returned `complete=true`, `profile_tax_id_present=true`, `provider_identity_present=true`, and `identity_alignment=matches`.
- `uv run aeat --format json config auth login --provider clave_movil --fresh --reset-lock` returned `authenticated=true`, `fresh=true`, `removed_sessions=0`, `acquired_lock=true`, and `reset_lock_state=absent`.
- `uv run aeat --format json config auth status --provider clave_movil` returned `configured=true`, `authenticated=true`, and `persisted_session_state=live`.
- `uv run pytest src/aeat/adapters/outbound/aeat/auth/tests/test_session_store_roundtrip.py -q` passed with 1 test, proving browser session persistence remains in the encrypted secure-object store.
- `AEAT_LIVE_TESTS_ENABLED=1 uv run pytest src/aeat/adapters/outbound/aeat/auth/tests/test_clave_movil_live.py::test_clave_movil_playwright_entrypoint_reaches_live_selector -m aeat_live -q` passed with 1 live selector probe.
- `uv run aeat --format json app live filed list --modelo 303 --from-year 2026 --to-year 2026` returned `row_count=0` and `failed_count=0`.
- `uv run aeat --format json app live filed pull --modelo 303 --year 2026` returned `captured_count=0`, `failed_count=0`, and no justificante metadata or filing stamps.
- `uv run aeat --format json app live expedientes pull --modelo 303 --year 2026` returned `declaration_count=0`, a persisted `snapshot_id`, and `failed_count=0`.
- `uv run aeat --format json app live notifications pull` returned `row_count=1` and a persisted `snapshot_id`.
- `uv run aeat --format json app live justificante list` returned `count=0`.
- `uv run aeat --format json app overview calendar --from 2026-01-01 --to 2026-12-31 --allow-incomplete` returned Modelo deadline entries with `justificante_required=true` and the pulled notification as a calendar message event.

## Notes

- This record closes only the authenticated session acquisition part of S08. S09 remains open because the full live auth pytest lane still contains credential/session dependent tests not rerun to no-skip green acceptance.
- S10 remains open because AEAT G313 returned no readable censo/Modelo 036 snapshot for the authenticated identity.
- S11 remains open because the all-model filed-history bulk read did not complete within 180 seconds, and no filed declaration row was available to prove justificante pull/enrollment.
- S12 and S13 have positive authenticated probes but remain broader plan rows until the full command groups are exercised and reviewed.
- S27 has positive calendar projection evidence for notifications and deadline filing evidence, but censo-derived obligation reconciliation remains blocked by the G313 censo result.

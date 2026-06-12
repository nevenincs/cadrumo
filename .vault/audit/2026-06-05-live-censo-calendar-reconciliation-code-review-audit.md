---
tags:
  - '#audit'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-05'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
  - '[[2026-06-05-live-censo-calendar-reconciliation-reference]]'
---

# `live-censo-calendar-reconciliation` Code Review

## CENSO-001 | HIGH | Explicit snapshot IDs were not profile-bound

`CensoSyncService.show_censo` resolved an explicit censo `snapshot_id` within the active bucket without checking that the resolved snapshot belonged to the requested `profile_id`. Because `compare_censo_with_profile` and `apply_censo_to_profile` both call `show_censo`, this could have compared or applied another profile's censo snapshot.

Resolution: fixed. `show_censo` now raises `errors.censo.snapshot_profile_mismatch` when the resolved snapshot profile differs from the requested profile. Added `test_show_refuses_explicit_snapshot_for_another_profile`.

## CENSO-002 | HIGH | IAE alone could derive activity income without natural-person proof

`_derive_profile_facts_from_censo` derived `taxpayer_type.irpf_income_categories = actividad_economica` whenever `activities.iae_epigraph` existed, even if the profile identity did not prove a DNI/NIE natural person. This was broader than the reference rule, which requires DNI/NIE profile identity plus G313 IAE evidence for this censo-derived bridge.

Resolution: fixed. IAE-derived `actividad_economica` is now conditional on proven natural-person identity. Added `test_apply_does_not_infer_income_category_without_natural_person_identity`.

## CENSO-003 | MEDIUM | JSON compare grouped lists were advertised but empty

`CensoCompareResult` exposed `diverging`, `censo_only`, and `profile_only`, but the CLI validated only the raw comparison dump, which did not serialize property-derived grouped buckets. Clients using the grouped JSON fields would receive empty lists.

Resolution: fixed. The CLI compare emitter now explicitly populates grouped row lists from the application comparison properties. The JSON compare test now asserts `payload["censo_only"]` contains the expected censo-only paths.

## CENSO-004 | LOW | Live-gate CLI regression only asserted nonzero exit

`test_refresh_refuses_without_live_gate` only asserted a nonzero exit code. An unrelated import error, active-profile error, or driver failure could have satisfied the test without proving the access-gate refusal.

Resolution: fixed. The test now asserts the refusal text includes the live-read gate message for `AEAT_LIVE_TESTS_ENABLED`.

## Verification

- Ruff passed on the touched Python files.
- Locale YAML parsed successfully for `en`, `es`, `ca`, and `hu`.
- Censo/profile CLI tests passed: 27 passed.
- Overview calendar and calendar CLI tests passed: 71 passed.
- Live active-profile checks remain externally blocked: no censo snapshot exists and AEAT G313 returned no readable censo for the configured NIF during live refresh.

## CENSO-005 | MEDIUM | W03 live censo acceptance remains blocked by AEAT pending Clave petition

The W03 live-refresh retry did not capture Modelo 036/G313 censo data. The local auth guard was first occupied by an orphaned `app live filed list` process from this verification run; after stopping that process, AEAT refused a new Clave Movil push because a previous petition was still pending on the AEAT server.

Resolution: open. The plan now tracks this as explicit live work instead of claiming the live calendar is complete. Steps `S06` and `S07` remain unchecked until a censo snapshot is captured, applied to the profile, and legal obligations project to calendar rows.

## CENSO-006 | LOW | Calendar live evidence projection is verified before censo enrolment

Persisted live expedientes and notifications project into the calendar event stream correctly, including Modelo 303 filing events with `justificante_verified` state. However, because every inspected profile currently has `taxpayer_model_declared = false`, these events are not yet attached to legal obligation rows for the active taxpayer model.

Resolution: accepted as phased state. Evidence projection is verified by W03 `S08`; obligation-row reconciliation remains open under W03 `S06` and `S07`.

## CENSO-007 | MEDIUM | Live-captured justificante evidence was not calendar-verified from filing records

`aeat_live_capture` is official AEAT justificante evidence in the live justificante reconciliation path and the cross-period clean-state gate, but overview filing evidence only promoted `aeat_justificante_pdf` to `justificante_verified`. A live-captured justificante stamped onto a filing record could therefore remain visible in the calendar as accepted/submitted but not justificante-verified.

Resolution: fixed. Overview filing evidence now treats both `aeat_justificante_pdf` and `aeat_live_capture` as `justificante_verified`, with a focused regression test.

## CENSO-008 | HIGH | Final live censo/calendar proof is blocked by encrypted profile-store unlock

The current shell can reach AEAT's live Clave selector, but profile-bound CLI reads require the encrypted secret-store master key. `AEAT_SECRET_PASSPHRASE` is not set, and the OS keychain backend returned a logon-session error before falling back to the passphrase backend. Consequently the run could not execute live `config profile censo pull`, apply the resulting Modelo 036/G313 snapshot, or prove active-profile legal obligation rows reconciled with live filing/message/justificante evidence.

Resolution: open. Added W04 steps to the plan for non-interactive profile-store unlock, full authenticated censo/filed-history/message/justificante pulls, and final active-profile calendar proof.

## CENSO-009 | HIGH | Noninteractive secret-store fallback hangs instead of refusing

The profile-bound CLI smoke for `app overview calendar` still timed out before any live AEAT call. A `faulthandler` probe showed the process blocked in `getpass.win_getpass` while the file-fallback master-key provider tried to prompt for the secret-store passphrase. In this automation shell, the prompt is not visible or answerable, so profile-bound live verification could hang indefinitely rather than returning the actionable CENSO-008 unlock blocker.

Resolution 2026-06-11: fixed for the hang path. `_default_passphrase_callback` now refuses when no configured `Settings.aeat_secret_passphrase` exists and either stdin or stderr is not interactive. Configured passphrase resolution remains unchanged. The real CLI smoke now exits promptly with `AEAT_SECRET_PASSPHRASE is not set and stdin is not interactive` instead of hanging. W04.P04.S09, S10, and S11 remain open because the encrypted profile store is still not unlocked and no authenticated censo/filed-history/message/justificante/calendar proof has been completed.

Verification 2026-06-11: `uv run pytest src/aeat/adapters/persistence/storage/master_key/tests/test_passphrase_failclosed.py src/aeat/adapters/persistence/storage/master_key/tests/test_master_key.py -q` passed with 62 tests. `uv run ruff check src/aeat/adapters/persistence/storage/master_key/_master_key_io.py src/aeat/adapters/persistence/storage/master_key/tests/test_passphrase_failclosed.py` passed. `uv run aeat --format json app overview calendar --from 2026-01-01 --to 2026-12-31 --allow-incomplete` returned the noninteractive passphrase refusal in about 3 seconds.

## CENSO-010 | MEDIUM | Live verification initially targeted stale shared profile instead of fresh user-created profile

The first W04 live-auth attempt tried to unlock the existing active profile store, which is not the operator path a new live user exercises. That confused an old shared-worktree custody problem with the product requirement: a user must be able to create a profile with their own passphrase and then run the live calendar/censo/filing surfaces from that profile.

Resolution 2026-06-11: fixed in verification procedure. W04.P04.S09 now creates an isolated fresh profile store with a fresh passphrase, proves `config profile create`, `config switch`, `config profile status`, overview calendar, and persisted live-snapshot list facades work under that passphrase, and only then attempts live AEAT pulls. The remaining blocker moved correctly to Cl@ve Móvil completion timeout, not profile-store unlock.

Verification 2026-06-11: fresh profile `live-user-smoke-20260611-1248` was created under isolated storage and a file-backend passphrase. Calendar returned Modelo 100/303/390/721 obligation rows with justificante-required evidence state. `app live filed list --modelo 303` and `config profile censo pull` reached the live Cl@ve non-QR route with matching NIE identity and timed out at `auth_completion_timeout`.

## CENSO-011 | HIGH | All-model filed listing aborted on one AEAT-unoffered Modelo

The authenticated all-model `app live filed list` run reached AEAT and queried the declaration register across registry modelos, but the command aborted when the sede did not offer Modelo `721`. That made the all-model filing-history facade brittle: one unsupported/unoffered modelo prevented the operator from receiving the successful rows and explicit failure inventory for every other modelo.

Resolution 2026-06-11: fixed. `app live filed list` now preserves fail-loud behavior for an explicit `--modelo`, but when no modelo filter is supplied it catches per-model failures, continues, and emits `failed_count` plus typed `failures` in the JSON payload using the same failure-row shape as `pull-all`. Typed `Period` values are stringified at the CLI boundary.

Verification 2026-06-11: `uv run aeat --format json app live filed list --from-year 2026 --to-year 2026` now succeeds with `row_count=0`, `failed_count=1`, and an explicit Modelo `721` AEAT-register failure. `uv run ruff check src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/_app_live_payloads.py` passed. `uv run pytest src/aeat/application/live/tests/test_filed_bulk_capture.py -q` passed with 3 tests.

## CENSO-012 | LOW | Locale scaffold drift remains outside the pull-only live CLI slice

The S14 audit found the live filed and expedientes acquisition surfaces consolidated on `pull`, with no remaining production `pull-all` command registration, locale leaf, or how-to example for the touched live surfaces. The remaining locale gate failure is broader catalogue drift: each locale still reports seven missing keys and five extra keys unrelated to the `pull` rename.

Resolution 2026-06-12: accepted as residual repository drift for this step. Focused documented-command conformance passed, and `rg` found no `pull-all` / `pull_all` tokens in the live CLI implementation, live locale catalogues, pull/file naming rule, or notification how-to guide. Full locale scaffold cleanup remains separate work.

Verification 2026-06-12: `uv run pytest src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/application/live/tests/test_filed_bulk_capture.py src/aeat/application/live/tests/test_justificante_capture.py src/aeat/application/live/tests/test_justificante_capture_resolution.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py src/aeat/entrypoints/cli/tests/test_live_justificante_verbs.py src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py -m "integration or not integration" -q` passed with 310 tests. Ruff passed for the touched live CLI and overview calendar surfaces. Live `config profile censo pull` still refused with no legible G313 censo, while live filed, expedientes, notifications, justificante, and calendar checks completed under the fresh profile.

## CENSO-013 | HIGH | IVA wallet history payload stringified typed Period rows

The S15 review found that `app live iva-wallet history` still passed `str(row.period)` into the payload row constructor. The payload schema expects the typed `core.Period`; stringifying there could reject valid history rows or weaken the typed Period boundary introduced by the period stringification work.

Resolution 2026-06-12: fixed. IVA wallet history result construction now preserves typed `Period` values in payload rows and leaves registry-token stringification to text output only. Added `test_live_iva_wallet_history_payload_preserves_typed_periods`.

## CENSO-014 | MEDIUM | Filed list output used display periods instead of registry period tokens

The S15 review found that live filed list text and failure rows could emit display strings such as `2026 1T` where the row already carries `year=2026` and should use the registry period token `1T`. This could make machine parsing and operator comparison drift from registry-backed period semantics.

Resolution 2026-06-12: fixed. Filed list result/line construction now emits registry period tokens for both successful rows and failure rows. Added `test_live_filed_list_payload_and_text_use_registry_period_tokens`.

## CENSO-015 | LOW | Pull-only CLI still had capture-all help key names

The S15 review found stale `capture_all_modelo_help` locale keys behind live `pull` options. The command surface had already consolidated on `pull`, but the locale key names still encoded the old verb and could reintroduce `pull-all` drift.

Resolution 2026-06-12: fixed through the locale CLI. Live filed and expedientes help keys are now `pull_modelo_help` across `en`, `es`, `ca`, and `hu`, and the stale `capture_all_modelo_help` keys were removed. Added `test_live_pull_help_locale_keys_do_not_use_capture_all_names`.

Verification 2026-06-12: `uv run ruff check src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/_app_live_expedientes_cli.py src/aeat/entrypoints/cli/tests/test_registry_cli.py` passed. `uv run pytest src/aeat/entrypoints/cli/tests/test_registry_cli.py -m integration -q` passed with 54 tests. The focused calendar/live/modelo gate passed with 440 tests. `uv run python -m aeat.locales scaffold --check` still fails on the previously recorded catalogue drift unrelated to the pull-only rename.

## CENSO-016 | INFO | Fresh-profile live calendar works, censo pull correctly refuses mismatched live identity

The S15 live smoke created an isolated file-backed profile and proved profile creation, profile status, and `app overview calendar --from 2026-01-01 --to 2026-12-31 --allow-incomplete`. The calendar returned Modelo 100/303/390/721 obligation rows with local filing readiness, AEAT submission observation, and justificante verification still represented as separate evidence states.

The subsequent live `config profile censo pull` attempt failed closed before accepting AEAT data because the Cl@ve identity did not match the active profile tax identity. This is the required safety behavior, but it means final Modelo 036/G313 censo-derived obligation reconciliation remains open until a matching taxpayer profile authenticates successfully.

## CENSO-017 | MEDIUM | Calendar evidence models allowed contradictory justificante state

The calendar builders produced consistent rows, but the typed boundary models did not reject contradictory evidence such as `aeat_submission_state = justificante_verified` with `justificante_verified = false`, or `justificante_verified = true` on merely observed submissions. A malformed persisted live event could therefore reach rendering with a self-contradictory filing state.

Resolution 2026-06-12: fixed. `OverviewCalendarFilingEvidence` and `OverviewCalendarEvent` now enforce the justificante state invariant at model validation time. Added application tests that construct contradictory evidence/events directly and assert they are refused.

Verification 2026-06-12: `uv run ruff check src/aeat/application/overview/_calendar.py src/aeat/application/overview/tests/test_calendar.py` passed. `uv run pytest src/aeat/application/overview/tests/test_calendar.py -q` passed with 54 tests. The focused calendar/live/modelo/cross-period gate passed with 442 tests.

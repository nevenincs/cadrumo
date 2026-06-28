---
tags:
  - '#audit'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-05'
modified: '2026-06-05'
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

## CENSO-018 | MEDIUM | Non-ALTA AEAT register rows could upgrade calendar filing evidence

The S17 audit focused on AEAT declaration-register status semantics. Live acquisition already prefers `ALTA` rows, but the overview projection had to enforce the same boundary when reading persisted local observations. Without that guard, a cancelled, superseded, or otherwise non-current AEAT row carrying a justificante artefact could be treated as submitted or justificante-verified calendar evidence for the obligation.

Resolution 2026-06-12: fixed. Calendar projection now requires `ALTA` before expedientes events, observed filing events, or persisted filed-declaration observations can produce or enrich per-obligation AEAT submitted/justificante evidence. Non-`ALTA` rows remain visible as historical calendar events with their raw status but do not upgrade the obligation state. Added application and CLI-storage regressions, including the late enrichment path where a non-`ALTA` event shares a reference id with separate verified evidence.

Verification 2026-06-12: `uv run ruff check src/aeat/application/overview/_calendar.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py` passed. `uv run pytest src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -m "integration or not integration" -q` passed with 66 tests. The focused calendar/live/modelo/cross-period gate passed with 445 tests. `vaultspec-code-reviewer` returned no findings; residual risk is limited to callers manually constructing `OverviewCalendarFilingEvidence` outside the guarded production merger.

## CENSO-019 | HIGH | Non-ALTA filed observations could enter official calculation history

The S18 audit moved the active AEAT register-state guard below the calendar and into the official live filed-observation persistence path. Before this hardening, `persist_filed_calculation_observation` accepted any `FiledDeclaracionObservation.status`, and bulk persistence ranked latest rows by timestamp/expediente id only. A later `BAJA` row could therefore be persisted as `aeat_sede_justificante` calculation history or IVA compensation history and become cross-period source data.

Resolution 2026-06-12: fixed. Direct filed-observation persistence now refuses non-`ALTA` rows. Bulk calculation-history and IVA-history selection rank active `ALTA` rows ahead of later non-active rows. The strict IVA history path skips non-`ALTA`-only periods without writing official history or aborting live acquisition.

Review 2026-06-12: `vaultspec-code-reviewer` initially found a HIGH failure-mode issue where the strict IVA path could raise on a non-`ALTA`-only period. The fix added the skip behavior and `test_iva_history_strict_persist_skips_non_alta_only_period`; re-review returned no findings. Residual risk: historical `aeat_sede_justificante` observations persisted before S18 may not carry source AEAT status metadata, so downstream readers cannot recover whether those old records came from a non-current register row.

Verification 2026-06-12: `uv run ruff check src/aeat/application/live/_filed_observation_persistence.py src/aeat/application/live/tests/test_filed_capture_calculation_history.py` passed. `uv run pytest src/aeat/application/live/tests/test_filed_capture_calculation_history.py -q` passed with 14 tests. The focused calendar/live/modelo/cross-period gate passed with 459 tests.

## CENSO-020 | HIGH | Official observation provenance needed taxpayer-bound AEAT register metadata

The S19 audit added encrypted source metadata to official `aeat_sede_justificante` calculation observations. New live filed-observation persistence now stamps AEAT register status, expediente id, and authenticated identity inside the AUDIT-class secure payload. Calendar projection uses this metadata when present: non-`ALTA` status refuses submission evidence, `ALTA` status can surface the expediente id as the AEAT reference, and stamped authenticated identity must match the active taxpayer.

Review 2026-06-12: `vaultspec-code-reviewer` initially found a HIGH issue because the calendar used stamped status and expediente id but did not compare stamped `authenticated_identity` to the active taxpayer. The fix threads `expected_tax_id` into calculation-observation projection and rejects mismatched stamped identities. Re-review returned no findings.

Verification 2026-06-12: `uv run ruff check src/aeat/application/calculations/_observations_repository.py src/aeat/application/live/_filed_observation_persistence.py src/aeat/application/overview/_calendar.py src/aeat/application/calculations/tests/test_observations_repository_roundtrip.py src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/application/overview/tests/test_calendar.py` passed. `uv run pytest src/aeat/application/calculations/tests/test_observations_repository_roundtrip.py src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/application/overview/tests/test_calendar.py -q` passed with 80 tests. The focused calendar/live/modelo/cross-period gate passed with 468 tests. Residual risk: older `aeat_sede_justificante` calculation observations without `source_metadata` still degrade as submitted evidence because no historical AEAT status or identity exists to validate.

## CENSO-021 | HIGH | Cross-period clean-state still accepts official observations without AEAT register provenance

S20 blocks stamped `aeat_sede_justificante` calculation observations when `source_metadata.aeat_register_status` is not `ALTA` or when `source_metadata.authenticated_identity` does not match the expected taxpayer/member. However, the provenance gate returns no blocker when `source_metadata` is empty, so an official-looking observation with no AEAT register status and no authenticated identity can still satisfy the cross-period clean-state filing gate if the separate filing/justificante checks pass.

This preserves the residual old-record risk recorded in CENSO-020 for the cross-period source path: a pre-stamp, manually seeded, or corrupted `aeat_sede_justificante` observation cannot prove it came from an active AEAT register row for the current authenticated identity, but it can still carry source values into a dependent filing as clean. The existing clean acceptance test continues to seed `aeat_sede_justificante` observations without metadata, so the suite locks in this bypass instead of proving stamped provenance is required.

Resolution 2026-06-12: fixed. Current `aeat_sede_justificante` source observations without stamped AEAT register provenance now produce `MISMATCHED_EXTERNAL_EVIDENCE_RECORD`; clean acceptance fixtures seed explicit `ALTA` register status and authenticated identity metadata; `test_cross_period_clean_state_blocks_missing_aeat_register_observation_provenance` covers the missing-metadata bypass.

Verification 2026-06-12: `uv run --no-sync ruff check src/aeat/application/calculations/_cross_period_clean_state.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py` passed. `uv run --no-sync pytest src/aeat/application/calculations/tests/test_cross_period_clean_state.py -q` passed with 28 tests.

Re-review 2026-06-12: PASS. The CENSO-021 bypass is closed for the cross-period clean-state path: empty `source_metadata` on `aeat_sede_justificante` observations now produces `MISMATCHED_EXTERNAL_EVIDENCE_RECORD`, the clean fixtures stamp `ALTA` status plus authenticated identity, and the missing-provenance regression covers a matching filing/justificante row with no observation metadata. No follow-up finding was identified.

## CENSO-022 | INFO | Live justificante stamping and pull-only drift re-review passed

S23 hardens `register_capture_as_filing_evidence`: a live-captured justificante is now parsed and matched against the current filing record before any `JustificanteRepository` save, `AEAT_LIVE_CAPTURE` external evidence stamp, `aeat_accepted = true`, or bucket event write. The match requires modelo, filing year, typed period, and taxpayer identity to agree. Missing profile tax identity or profile-storage load failure refuses the stamp instead of treating the receipt as verified evidence.

The real-behavior regression tests use the real Modelo 130 justificante fixture and parser. They prove modelo, filing-year, period, and taxpayer mismatches all refuse before saving the justificante or marking the filing accepted; the taxpayer test edits the active profile through the user-profile orchestration layer rather than mutating repository internals.

S24 re-verified the CLI pull/file standard after backend and `Period` drift: live filed and expedientes bulk reads remain exposed through `pull` with bulk options, and `pull-all` is not registered.

Live verification 2026-06-12 used a fresh isolated file-backed profile under `var/live-user-smoke/20260612-s23` with a process-local development passphrase. `config profile create`, `config profile status`, and `app overview calendar --from 2026-01-01 --to 2026-12-31 --allow-incomplete` succeeded. The calendar derived Modelo 100, 303, 390, and 721 entries and kept local readiness, AEAT submission observation, and justificante verification separate. `config profile censo pull` reached AEAT and refused closed because G313 returned no readable censo for the profile identity. `app live filed pull --from-year 2026 --to-year 2026` succeeded under `app.live.filed.pull` with `mode = bulk`, `captured_count = 0`, and `failed_count = 8`. `app live expedientes pull --from-year 2026 --to-year 2026` succeeded under `app.live.expedientes.pull` with one persisted snapshot and no declarations. `app live notifications pull` persisted one AEAT notification snapshot, and the subsequent overview calendar projected it as a message event. `app live justificante pull --modelo 303 --year 2026 --period 1T` reached the authenticated live path and refused because no filed declaration exists for that period, so justificante verification correctly remained false.

Review 2026-06-12: `vaultspec-code-reviewer` returned no findings. The reviewer noted that year and period mismatches were covered by the predicate but not explicit tests; this was resolved immediately by adding dedicated real-PDF tests for both cases. No residual S23/S24 review findings remain.

Verification 2026-06-12: `uv run ruff check src/aeat/application/live/_justificante.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py src/aeat/application/calculations/_cross_period_clean_state.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/overview/_calendar.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/_overview.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_registry_cli.py` passed. `uv run pytest src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py -q` passed with 11 tests. `uv run pytest src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/overview/tests/test_calendar.py -q` passed with 101 tests. `uv run pytest src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_registry_cli.py -m integration -q` passed with 63 tests.

## CENSO-023 | INFO | Bare AEAT acceptance no longer upgrades calendar state

S25 closes a calendar-side evidence weakness: `aeat_accepted = true` on a local filing record no longer renders as AEAT `accepted` unless the record also carries an external evidence reference. This keeps a bare boolean from being presented as real AEAT submission evidence. Cross-period already blocked the same shape through `MISSING_EXTERNAL_EVIDENCE`; S25 adds the exact regression there as well so the invariant is tested in both calendar projection and filing-grade dependency checks.

S25 also canonicalizes taxpayer identity comparisons across the three evidence gates touched by this campaign: calendar justificante lookup, filed-declaration observation identity matching, external import justificante binding, and cross-period justificante matching now compare trimmed upper-case tax IDs. Wrong identities still fail; casing drift no longer blocks a valid AEAT-bound receipt.

Review 2026-06-12: `vaultspec-code-reviewer` returned no findings. The reviewer noted a residual missing exact cross-period fixture for `aeat_accepted = true` with no `external_evidence`; this was resolved before closeout with `test_bare_aeat_acceptance_without_external_evidence_does_not_clear_cross_period_gate`.

Verification 2026-06-12: `uv run ruff check src/aeat/application/overview/_calendar.py src/aeat/application/overview/tests/test_calendar.py src/aeat/application/modelo/_external_import_actions.py src/aeat/application/modelo/tests/test_import_flow.py src/aeat/application/calculations/_cross_period_clean_state.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py` passed. `uv run pytest src/aeat/application/overview/tests/test_calendar.py src/aeat/application/modelo/tests/test_import_flow.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py -q` passed with 121 tests. `uv run pytest src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -m integration -q` passed with 9 tests.

## CENSO-024 | HIGH | ModeloRecord copy updates bypassed the AEAT-evidence invariant

S26 moved the bare-acceptance guard down to the `ModeloRecord` domain boundary so normal filing records cannot carry `aeat_accepted = true` unless they also carry an `external_evidence` reference. The first review found a high-severity bypass: Pydantic v2 `model_copy(update=...)` skips validators, so code could still flip the acceptance bit on an otherwise valid record without evidence.

Resolution 2026-06-12: fixed. `ModeloRecord.model_copy(update=...)` now revalidates updated copies through the normal model validator path. The domain tests cover both direct construction and copy-update bypass attempts. Downstream defensive tests that intentionally model corrupt legacy records now use explicit `model_construct`, so normal domain APIs remain closed while legacy-read behavior stays testable.

Review 2026-06-12: `vaultspec-code-reviewer` re-reviewed the S26 patch and returned PASS. The reviewer verified that normal domain paths now reject AEAT acceptance without external evidence, the remaining `model_construct` usage is explicit corrupt/legacy fixture setup, typed `Period` survives the copy/revalidation path, and the scoped 106-test gate passed.

Verification 2026-06-12: `uv run ruff check src/aeat/domain/modelos/_filing_record.py src/aeat/domain/modelos/tests/test_filing_record_repository_roundtrip.py src/aeat/application/overview/tests/test_calendar.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py` passed. `uv run pytest src/aeat/domain/modelos/tests/test_filing_record_repository_roundtrip.py src/aeat/application/overview/tests/test_calendar.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py -q` passed with 106 tests. `uv run pytest src/aeat/application/modelo/tests/test_import_flow.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py src/aeat/application/modelo/tests/test_file_flow_filing.py src/aeat/application/modelo/tests/test_amend_flow.py -q` passed with 60 tests. `uv run pytest src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_registry_cli.py -m integration -q` passed with 63 tests.

## CENSO-025 | HIGH | External evidence without AEAT acceptance could still look submitted

S27 closes the inverse half-stamped state. After S26, a bare `aeat_accepted = true` without `external_evidence` was impossible through normal domain paths. However, the opposite torn shape, `external_evidence` with `aeat_accepted = false`, could still be projected by the calendar as submitted or justificante verified because the projection treated the evidence reference itself as enough for AEAT state upgrade.

Resolution 2026-06-12: fixed. `ModeloRecord` now rejects `external_evidence` unless `aeat_accepted` is also true, including through `model_copy(update=...)`. Calendar projection still handles explicitly constructed corrupt legacy records defensively, but evidence without acceptance remains local external-baseline state and does not upgrade AEAT submission or justificante verification.

Review 2026-06-12: `vaultspec-code-reviewer` reviewed S27 and returned PASS.

Verification 2026-06-12: `uv run ruff check src/aeat/domain/modelos/_filing_record.py src/aeat/domain/modelos/tests/test_filing_record_repository_roundtrip.py src/aeat/application/overview/_calendar.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_modelo.py src/aeat/application/modelo/tests/test_import_flow.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py` passed. `uv run pytest src/aeat/domain/modelos/tests/test_filing_record_repository_roundtrip.py src/aeat/application/modelo/tests/test_import_flow.py src/aeat/application/overview/tests/test_calendar.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py src/aeat/entrypoints/cli/tests/test_modelo.py -m "integration or not integration" -q` passed with 235 tests. `uv run pytest src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_registry_cli.py -m integration -q` passed with 63 tests. `uv run vaultspec-core vault plan check .vault/plan/2026-06-05-live-censo-calendar-reconciliation-plan.md` passed.

## CENSO-026 | MEDIUM | Text censo-apply obligation rows omit required deadline and state fields

W03.P03.S28 requires both JSON and text `config profile censo apply` output to expose concrete calendar obligation rows with filing year, typed period token, opens/closes/adjusted dates, payment cutoff, and state. The JSON payload row built in `src/aeat/entrypoints/cli/_config/_profile_censo.py` includes `closes_on`, `payment_cutoff_on`, `status`, and `user_state`, but the text renderer only emits `modelo`, `filing_year`, `period`, `opens_on`, and `adjusted_closes_on` on each `calendar_obligation` line.

This leaves the human/tabular CLI surface unable to reconcile normal close date versus adjusted close date, direct-debit cutoff, or current filing state after censo apply. The current text regression only asserts that a `calendar_obligation	303` line exists, so it would not catch the missing fields. JSON output and the application-level test do prove censo-derived taxpayer axes can produce a real Modelo 303 filing window, so this is a text contract gap rather than a calendar-projection failure. S06/S07 should remain advanced only as local censo-derived projection proof; this does not close the live G313 proof gap.

Resolution review 2026-06-12: PASS. CENSO-026 is resolved for the local censo-apply CLI contract: `_calendar_summary_after_apply` now builds `calendar_obligation_rows` after taxpayer-model reconciliation with modelo, filing year, registry period token, `opens_on`, `closes_on`, `adjusted_closes_on`, `payment_cutoff_on`, `status`, and `user_state`; text mode emits the same concrete row fields, and JSON exposes the row list through `CensoApplyPayload`. Focused review verified the text test parses a current-year Modelo 303 row and validates deadline ordering plus state fields, while the JSON test validates the same row and deadline ordering. Residual risk: JSON tests do not explicitly assert `payment_cutoff_on`, `status`, and `user_state`, and live G313 proof remains separate from the fixture-backed local censo projection.

Post-review hardening 2026-06-12: the JSON censo-apply test now explicitly asserts `payment_cutoff_on`, `status`, and `user_state` on the current-year Modelo 303 obligation row. Live G313 proof remains tracked separately from the fixture-backed local censo projection.

## CENSO-027 | INFO | S29 pull-only live CLI drift guard review passed

Review 2026-06-12: PASS. The S29 change adds a real command-tree guard in `src/aeat/entrypoints/cli/tests/test_registry_cli.py` that walks the materialized `app live` Typer subtree, rejects any descendant command named `pull-all` or `capture-all`, and asserts the live filed and expedientes read facades still expose `pull`. The review found no issue in the helper or assertions: lazy `app live` loading is exercised through the actual Click/Typer command tree, the live subcommands are regular Typer groups, and active live CLI source scans showed no hidden or explicit `pull-all` / `capture-all` registrations.

Verification credited from S29: `uv run ruff check src/aeat/entrypoints/cli/tests/test_registry_cli.py` passed; `uv run pytest src/aeat/entrypoints/cli/tests/test_registry_cli.py -m integration -q` passed with 55 tests; literal active-source scans for `pull-all` and `capture-all` only found the guard assertions in tests. Residual risk is limited to future command-registration mechanisms outside Typer's command registry or intentionally hidden aliases; neither pattern is present in the reviewed live CLI files.

## CENSO-028 | INFO | S31 censo-derived enrolment provenance review passed

Review 2026-06-12: PASS. The S31 censo-apply CLI change reloads the persisted profile after `apply_censo_to_profile`, builds calendar rows from that record, and extracts enrolment provenance from censo-stamped profile facts rather than from calendar rows alone. Text output now emits `calendar_enrolment_sources` and per-row `enrolment_sources=...`; JSON exposes the same values through `calendar_enrolment_source_paths` and each `calendar_obligation_rows` entry. The reviewed tests assert the expected censo source stamps for `activities.iae_epigraph`, `taxpayer_type.entity_type`, and `taxpayer_type.irpf_income_categories` in both text and JSON. Residual risk: row provenance is a profile-level source-path list attached to each obligation row, not a per-modelo dependency graph; live G313 proof remains separate from the local fixture-backed censo projection.

## CENSO-029 | INFO | S32 per-modelo censo enrolment provenance review passed

Review 2026-06-12: PASS. S32 narrows censo-apply calendar row provenance through `calendar_applicability_profile_keys_for_modelo`, exported at the overview application boundary and derived from the canonical modelo applicability rule table plus IVA regime gating. The censo CLI now intersects censo-stamped enrolment facts with each row's Modelo-specific applicability keys, and adds raw `activities.iae_epigraph` support only when the row depends on censo-derived `taxpayer_type.irpf_income_categories`. The summary-level `calendar_enrolment_source_paths` remains the full censo enrolment source list.

The reviewed text and JSON regressions prove the intended split: Modelo 303 rows carry `activities.iae_epigraph=aeat_censo_read`, `taxpayer_type.entity_type=aeat_censo_derived`, and `taxpayer_type.irpf_income_categories=aeat_censo_derived`; Modelo 100 rows carry only `taxpayer_type.entity_type=aeat_censo_derived`. No source-path overexposure or schema/export issue was identified. Verification credited from S32: scoped ruff passed, focused censo CLI tests passed with 11 tests, overview plus censo tests passed with 27 tests, JSON schema plus censo tests passed with 103 tests, and the broader censo/calendar/overview gate passed with 53 tests.

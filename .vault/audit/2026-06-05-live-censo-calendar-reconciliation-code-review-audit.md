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

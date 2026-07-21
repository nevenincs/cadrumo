---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-11'
modified: '2026-07-04'
step_id: 'S06'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# W03.P03.S06 - reconcile censo snapshot into profile-derived taxpayer model and obligation enrolment facts

## Scope

- `src/aeat/application/user_profile/_censo_sync.py`

## Description

- Reconcile a censo snapshot into profile-derived taxpayer facts through `CensoSyncService.apply_censo_to_profile`, which reads the persisted snapshot and derives the taxpayer axes with `_derive_profile_facts_from_censo`.
- Derive the taxpayer model (`taxpayer_type.entity_type`) and obligation enrolment axis (`taxpayer_type.irpf_income_categories`) from the censo NIE/NIF identity plus the IAE epigraph, and stamp each derived fact with the `CENSO_DERIVED_SOURCE_TAG` provenance source.
- Refuse to infer an income-category obligation when the snapshot lacks IAE evidence, or when the identity is not a natural person - no silent obligation inference.
- Prove the reconcile against real censo-snapshot fixtures (the in-test `fact_source` callable), not a live AEAT pull: the reconcile is snapshot-shape-agnostic, so a fixture snapshot and a live-pulled one flow through the identical apply path.

## Outcome

- The reconcile is implemented and verified at HEAD. `apply_censo_to_profile` returns `derived_paths == ("taxpayer_type.entity_type", "taxpayer_type.irpf_income_categories")`, sets `entity_type = natural_person` and `irpf_income_categories = actividad_economica`, and stamps both with `CENSO_DERIVED_SOURCE_TAG`.
- Fixture-proven, real-behavior (no mocks, no live pull, real `SecureObjectRepository`): `test_censo_sync.py` = 17 passed (-n0). The pivotal reconcile assertion is `test_apply_derives_taxpayer_axes_from_nie_and_iae_for_calendar`; the no-silent-inference gates are `test_apply_does_not_infer_income_category_without_iae` and `test_apply_does_not_infer_income_category_without_natural_person_identity`.
- The provenance stamp is proven by `test_apply_stamps_censo_facts_with_provenance_tag`, and the home-office usage-ratio seeding by `test_apply_seeds_home_office_usage_ratios_from_censo` (idempotent per `test_apply_seeding_idempotent_on_repeat`).

## Notes

- Scope split: this record is the S06 reconcile scope only. The paired S07 record covers the calendar projection. The record originally combined S06+S07 (non-standard `step_id: 'S06-S07'`); it is normalized to the vaultspec 1:1 Step-to-exec convention as the S06 record, with the S07 record scaffolded separately.
- LIVE proof handed to W04: the reconcile above is the fixture-provable scope. Pulling a real Modelo 036 / G313 censo snapshot against a live profile and applying it is a distinct, AEAT-gated concern owned by `W04.P04.S10` (rerun live censo pull/compare/apply) and `W04.P04.S11` (prove live submitted / justificante evidence), both intentionally left open. Nothing here asserts a live pull occurred.
- Where the reconcile landed: `c9d1a496f0` (added `_derive_profile_facts_from_censo`), `432a69ac09` (the fixture-backed reconcile test plus the two negative no-silent-inference gates), and the sibling W03.P03 CLI/calendar-row exposure steps already closed (S28/S31/S32); test-harness hardening to the uuid profile-identity invariant rode `c258654999` / `df7b0d50cd`. An earlier 2026-06-11 pass on this record attempted a live profile-bound pull and could not complete it because the active encrypted secret store required an interactive `AEAT_SECRET_PASSPHRASE`; that live-proof concern is exactly what W04 tracks.

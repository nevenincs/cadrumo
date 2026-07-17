---
tags:
  - '#exec'
  - '#censo-operator-manual-enrolment'
date: '2026-07-11'
modified: '2026-07-17'
step_id: 'S11'
related:
  - "[[2026-07-11-censo-operator-manual-enrolment-plan]]"
---

# Re-seat bound_raw_afectacion_ratio onto operator-declared vivienda_office m2 profile facts, delete the producerless censo snapshot substrate (module, namespace, custody resolver, re-exports, error entry + locale leaves, api stub, tests), reconcile away CENSO_CORROBORATED + censo_snapshot_id, and add real-behavior guard tests

## Scope

- `src/aeat/application/user_profile/_censo_sync.py`
- `src/aeat/application/live/_censo.py`
- `src/aeat/adapters/persistence/storage/_namespace_registry.py`
- `src/aeat/application/calculations/_cross_period_models.py`

## Description

- Re-seat `CensoSyncService.bound_raw_afectacion_ratio` to derive `office_m2 / total_m2` from the operator-declared `vivienda_office` m2 facts on the encrypted profile record (`UserProfileLifecycleRepository.load` + `record_to_path_values`) instead of the retired `CensoSnapshotService.latest_active(...).censo_facts`; drop the `snapshots` constructor seam, add a `profiles` seam, keep the call-site signature stable.
- Delete the producerless snapshot substrate: the `application/live/_censo.py` module and its `CensoSnapshot` / `CensoSnapshotService` / `CensoSnapshotRepository` / `CensoSnapshotNotFoundError` / `censo_snapshot_object_key` / `derive_censo_snapshot_id` symbols, the `live_censo_snapshot` secure-object namespace, the `aeat.application.live.censo_snapshot` custody-carry resolver, the `application/live` and storage `__all__` re-exports, the `REFUSED_LIVE_CENSO_SNAPSHOT_NOT_FOUND` error-registry entry and its four locale leaves (via the locales CLI), the generated api stub (via apidocs scaffold), and the substrate tests.
- Reconcile away `NoPriorObligationProvenanceKind.CENSO_CORROBORATED` and `NoPriorObligationProvenance.censo_snapshot_id`; simplify the validator to accept `OPERATOR_DECLARED` as the sole provenance kind; refresh the stale `censo-corroborated when the live censo surface is fixed` comments.
- Reseat the ledger preflight and ratios-CLI test scaffolding onto operator-declared profile facts; add real-behavior guard tests.

## Outcome

- The `config profile edit` refusal in the home-office censo guard is a true, live instruction again: the guard, `derive_home_office_ratios_from_censo`, `censo_override_warning`, `censo_business_pct_for`, and `CensoRatioMismatchError` are kept intact and now resolve their ratio from operator-declared facts.
- Guard tests added: `bound_raw_afectacion_ratio` from real profile facts (present -> office/total, partial -> None, bounds/parse defenses); a single-profile regression proving an override with facts absent refuses naming `config profile edit` and that declaring the facts clears the refusal; a matching override passes and a diverging one refuses naming both values; the classify path stamps the derived business_pct when the operator omits one and facts are present.
- Gates: ruff clean on all touched files; `python -m aeat.locales scaffold --check` shows extra=0 for this change (the residual missing=30 is unrelated peer drift); `python -m dev.docs.apidocs scaffold --check` conformant; full-tree `pytest --collect-only -q` clean (12743 collected, zero collection errors); touched-suite run 1434 passed with the single red being a pre-existing peer `test_exception_base_hygiene` failure for the m210 `Modelo210AgrupacionRentaRowsError` class.

## Notes

- CENSO_CORROBORATED deletion decision: DEFAULT reject-and-delete applied. No production site ever constructed the member or set `censo_snapshot_id` (every `NoPriorObligationProvenance` site is `OPERATOR_DECLARED`), and the containing `CrossPeriodDependencyEvidence` is computed fresh at calculate time (not a persisted shape), so deletion strands no data and needs no upgrader.
- The `CENSO_SOURCE_TAG` / `CENSO_DERIVED_SOURCE_TAG` markers and the overview calendar's `live_censo_verified_profile_keys` path are intentionally KEPT: nothing stamps them, so the verified-key set stays empty and the `censo.enrolment_unverified` posture is preserved — the honest default the ADR mandates.
- apidocs scaffold regenerated peer-owned stubs (new peer modules `_attribution_received_advisory`, `_m210_agrupacion_renta`, `_m303_settlement`); those were restored to HEAD and the two untracked peer stubs removed so only the `_censo` stub removal and the `application/live` toctree edit are staged.
- Not owned by this change: the pre-existing peer `test_exception_base_hygiene` m210 failure and the locales missing=30 peer drift, both flagged in the dispatch brief.

---
tags:
  - '#exec'
  - '#iva-compensation-override-cli'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S01'
related:
  - "[[2026-06-19-iva-compensation-override-cli-plan]]"
---

# Add record_iva_compensation_override_for_bucket: resolve NIF, build IvaCompensationOverride(amount, reason, evidence_locator, recorded_at), drive reconcile_modelo_303_iva_compensation with override and persist the taxpayer_override decision

## Scope

- `src/aeat/application/modelo/_iva_wallet_seed.py`

## Description

- Add `record_iva_compensation_override_for_bucket` to the modelo IVA-wallet application facade.
- Resolve the active bucket to a taxpayer NIF through the shared `taxpayer_nif_for_bucket` gate, refusing when absent.
- Refuse a negative amount, mirroring the seed and correct recorders.
- Guard the filed basis: refuse when a sealed Modelo 303 revision at or after the period already consumed the compensación basis.
- Refuse to overrule fresh AEAT evidence: refuse when a non-blocked `aeat_wallet` decision already resolves the period.
- Build an `IvaCompensationOverride(amount, reason, evidence_locator, recorded_at)` and drive `reconcile_modelo_303_iva_compensation` with `persist=True` to store the non-blocking `taxpayer_override` decision through the single decision repository.

## Outcome

- The recorder persists exactly one `taxpayer_override` decision keyed by period, consumed by the calculate path via `apply_iva_compensation_decision_binding` onto casilla 110.
- Verified green by the override behaviour suite exercising real persistence.
- Contacts AEAT zero times; records a local decision only, upholding the no-live-write safety gate.

## Notes

- The recorder implementation was present at HEAD when this record was authored; this Step verified it against real gates and closed it with an execution record. The originating plan was at 0/8 with the implementation already committed and unrecorded.
- `reason` and `evidence_locator` are mandatory operator-asserted provenance recorded for the audit trail; the app does not fetch or verify external evidence.

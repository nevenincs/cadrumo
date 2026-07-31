---
tags:
  - '#exec'
  - '#m303-refund-fichero-block'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:2bd2fd2fe1608e874432eaa28575bfc7e7ed30661b0ef778c396aa084f0520ed'
step_id: 'S02'
related:
  - "[[2026-06-24-m303-refund-fichero-block-plan]]"
---

# Add the typed refund-account carrier grouping iban and the new fields, with an IBAN structural field validator that rejects a malformed IBAN at the boundary

## Scope

- `src/aeat/domain/deadlines/_models.py`

## Description

- Add the typed `RefundAccount` carrier model to the deadlines domain models, grouping the optional `iban` with the `swift_bic`, `bank_name`, `bank_address`, `bank_city`, `bank_country_code`, and derived `sepa_marca` fields.
- Add an IBAN structural field validator that runs in before-mode: canonicalise the input, treat `None` and blank as "no account on file", and reject a malformed IBAN at the secure-storage boundary.
- Reuse the shared core primitives `IBAN_SHAPE_RE` and `iban_mod_97` for the shape and mod-97 checks rather than re-implementing IBAN validation, raising the domain `DeadlineValidationError` on a shape miss or a mod-97 failure.

## Outcome

- `RefundAccount` is defined in `src/aeat/domain/deadlines/_models.py`, importing `IBAN_SHAPE_RE`, `iban_mod_97` from `...core`, and is exported from the deadlines package facade.
- The `_validate_iban` before-validator rejects a shape-invalid or mod-97-invalid IBAN with `DeadlineValidationError` and passes `None` through as no-account-on-file.
- The refund-account persistence roundtrip test class exercises the validator directly: a valid IBAN is accepted and canonicalised, `None` passes through, and malformed input is refused. All pass at HEAD.

## Notes

- This record documents the verified landed state at HEAD.
- IBAN validation reuses the single canonical core home per the schema-central-config authority; no parallel IBAN regex or mod-97 routine was introduced.

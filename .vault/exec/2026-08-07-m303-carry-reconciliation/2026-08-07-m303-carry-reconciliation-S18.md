---
tags:
  - '#exec'
  - '#m303-carry-reconciliation'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:a489037be181ef74f5cf6d7bf3207d4919f581c62c5bccb9c7cdb8eeee621d8d'
step_id: 'S18'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
  - "[[2026-08-09-m303-carry-reconciliation-s18-code-review-audit]]"
---
# S18 charge-account public export verification

## Scope

- `src/cadrumo/domain/deadlines/`
- `src/cadrumo/application/user_profile/`
- `src/cadrumo/application/modelo/`
- `src/cadrumo/entrypoints/cli/`
- `src/cadrumo/locales/`

## Description

- Preserve a distinct encrypted `ChargeAccount` profile fact rather than reusing the refund account.
- Project the charge account through the canonical taxpayer boundary into Modelo 303 export.
- Require a charge IBAN for U and render only that IBAN on the DID page.
- Refuse U when charge-account data is absent despite a persisted refund account.
- Re-review the original public-path gap after S20 supplied the canonical semantic U election.

## Outcome

S18 is complete. The original review finding is resolved by a public Modelo 303 path from persisted profile facts through canonical projection and `PaymentElection.DOMICILIACION` to `export_modelo_revision`. The rendered U DID contains only the charge IBAN. Refund output remains tied to the refund account, and missing charge data fails closed.

## Verification

`uv run --no-sync pytest -q src/cadrumo/application/modelo/tests/test_export_output_paths.py::test_public_domiciliacion_export_projects_persisted_charge_iban_to_did_only src/cadrumo/application/modelo/tests/test_export_output_paths.py::test_public_domiciliacion_without_persisted_charge_account_refuses src/cadrumo/application/modelo/tests/test_export_refund_did.py`

`6 passed in 16.97s`

The independent S18 re-review confirmed that the prior MEDIUM public-U-composition finding is cleared and that the refund DID tests retain refund-account-only behavior.

## Notes

The public U path depends on S20's canonical payment-election resolver. S18 remains limited to the distinct charge-account persistence, projection, and charge-only DID composition capability; G remains capability-refused and does not consume charge-account data.

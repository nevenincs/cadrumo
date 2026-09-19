---
tags:
  - '#audit'
  - '#m303-carry-reconciliation'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:bd8c13b51bde27d4283df2a0c598aae631ef7ee23cabc32877d4fb9d7a2b9766'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
---
# `m303-carry-reconciliation` audit: `M303 S18 charge-account export review`

## Scope

Independent review of S18's separate encrypted charge-account persistence, profile projection, generated CLI entry surface, Modelo 303 DID composition, error registry and four locale catalogues. The review also checked the focused real encrypted-SQL, export rendering, refund-regression, and CLI-persistence tests against the S18 plan and related ADR.

## Findings

### public-u-composition-reach | medium | The U branch has no real public-path proof

The U tests call the private `_compose_charge_account_block` and render manually assembled headers, rather than reaching the block through `compose_export_headers` or `export_modelo_revision`. That matters because the public composer always resolves the declaration type through `resolve_modelo_result_disposition`, whose only operator input is `RefundElection` with `COMPENSAR` and `DEVOLVER`; the resolver derives a positive Modelo 303 result as `I` and has no recorded U/G payment-method election. The new charge-IBAN data path is consequently shown at the private composer and renderer seams but not from a real public U selection. S18 lifecycle closure is held pending the architecture ruling on canonical U/G election ownership.

## Recommendations

- Decide the authoritative recorded U/G payment-method election and thread it through the single result-disposition resolver, export, filing, quickfile, and CLI paths as appropriate; do not add a test-only declaration-type override.
- After that decision, add real public export/composition tests for a selected U with a persisted/projected charge IBAN and for its missing-charge refusal, then rerun review before closing S18.
- Resolution (re-reviewed): S20 now provides the canonical `PaymentElection` and the public export proof. Persisted profile facts project a distinct charge account, `DOMICILIACION` resolves to `U`, and `export_modelo_revision` renders the DID page with only that charge IBAN. The missing-charge path refuses despite a refund account, while the refund DID regressions retain refund-account-only output. The focused six-test suite passed; this MEDIUM finding is cleared.

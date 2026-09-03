---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v1'
related:
  - '[[2026-08-11-tui-architecture-plan]]'
  - '[[2026-09-02-unreachable-capability-tui-navigation-join-adr]]'
  - '[[2026-09-02-unreachable-capability-tui-homepage-product-design-research]]'
---

# `tui-architecture` audit: `w08 p27 s391 review`

## Scope

Independent review of `W08.P27.S391` across `src/cadrumo/application/ledger/workspace.py`, its focused tests, the promotion of `application.aggregation.ledger_filing_snapshot` to a public defining module, and all live imports of that authority. The review covered the exact seven Ledger areas, source/status/availability meaning, affected-declaration joins, deterministic pure construction, sensitive serialization, local-versus-AEAT evidence separation, import direction, facade and legacy removal, and current caller/test parity.

The projection and every nested record use strict frozen Pydantic configuration. It serializes stable transaction, invoice and calculation-revision identifiers, natural declaration coordinates, booleans and counts while excluding descriptions, counterparties, tax identifiers, invoice contents, amounts and source paths. All declared sources are local and no AEAT state is projected. The builder receives preloaded catalogues and pure readers and contains no adapter, entrypoint, repository, filesystem or network dependency. The filing-snapshot implementation now has one public defining module, the displaced underscore module is absent, all observed consumers import the defining module directly, and the aggregation package facade no longer forwards its symbols.

## Findings

### foreign-invoice-bucket-admission | high | Foreign-profile invoices can enter a Ledger workspace reconciliation

`project_ledger_workspace` binds the snapshot bucket from the Ledger summary and rejects a differently keyed review or preflight report. It never checks `Invoice.bucket_id` for any member of the supplied invoice catalogue. The canonical suggestion and link-consistency readers consume every supplied invoice, so an invoice explicitly belonging to a different profile can be compared with this Ledger's transactions and its stable invoice identifier emitted in `invoice_reconciliations` or `link_inconsistencies`. The affected-declaration path correctly refuses a cross-bucket WorkUnit, but the parallel invoice join has no such boundary. This is a real cross-profile local-data conflation, not only missing test coverage.

### contradictory-input-snapshot | medium | Review and summary facts are not reconciled with the canonical transaction catalogue

Only bucket labels are compared. `review_transaction_ids` is copied from the review result without checking that each identifier exists in the supplied transaction catalogue, and the summary's total/active counts are not checked against the entry set used by the same projection. A bucket-matching but stale or mismatched review result can therefore expose a review target absent from `entries`, while the area counts describe a different snapshot. The provider claims callers hand it one snapshot, but does not establish that invariant at its owning boundary.

### area-contract-test-coverage | medium | Tests do not pin the exact seven-area source, status, availability and count matrix

The focused test proves canonical enum order, that every source string begins with `local.`, and one Review status. It does not assert the exact source tuple, availability, status and item count for each of the seven areas. Swapping the Evidence and Reconciliation authorities, marking Import ready, or deriving a wrong Classification count would remain green. The availability test constructs one area record directly and proves a missing reason is rejected; it does not prove the workspace builder's complete area projection. A positive affected-declaration test is also absent, so natural Modelo/year/period projection, changed/removed counts and canonical ordering are not acceptance evidence even though the implementation appears correct by inspection.

## Recommendations

1. Before invoking either invoice reconciliation reader, reject every invoice whose non-null `bucket_id` differs from the Ledger summary bucket. Add a detector using a fully validated foreign-bucket invoice and prove neither suggestions nor inconsistencies can cross the boundary.
2. Require every review identifier to resolve in the supplied transaction catalogue and reconcile snapshot counts at the boundary, or replace the independently supplied summary/review facts with one canonical snapshot input that makes disagreement unrepresentable.
3. Assert a literal seven-row expectation covering area, exact ordered sources, availability, reason absence/presence, status and item count. Add positive affected-declaration cases with multiple deliberately unordered stale revisions and exact natural-address/count expectations.
4. Focused Pytest passed 30 tests across the Ledger workspace and canonical filing-snapshot/evidence authorities. Ruff and ty passed; Basedpyright reported zero errors, warnings or notes. The public-module promotion and caller updates are clean, but one high and two medium findings remain open. `W08.P27.S391` must not close.

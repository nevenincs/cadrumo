---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:a9855e5fa0e172a1862d690964048047d87b2a93ee39004cdfca515e18c71e47'
step_id: 'S38'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Let the income aggregation read a linked sales invoice for its base, cuota and retencion, following the derive-on-read shape the expense pipeline already proves

## Scope

- `src/cadrumo/application/aggregation/_renta_income_ledger.py`

## Description

- Add `_SalesInvoiceEvidencePayload` and `_sales_invoice_evidence_payload` in `src/cadrumo/application/aggregation/_renta_income_ledger.py:566`, mirroring the expense pipeline's derive-on-read shape.
- Assert the credited amount against the invoice total NET of its declared retencion, not against the gross.
- Give the linked invoice's base precedence over the transaction substrate at the observation site, with the transaction field as fallback.
- Prefer the invoice-declared retencion over the bounded inference, carrying `LedgerWithholdingDerivation.DECLARED_ON_LINKED_INVOICE` from `src/cadrumo/core/aggregation.py:520`.
- Add five per-guard issue reasons rather than one generic mismatch.
- Thread the invoice catalogue through the classifier and both aggregators, and the invoice repository through both `*_from_repositories` entry points via `_load_income_invoices`.
- Wire the single production call site in `src/cadrumo/application/aggregation/_modelo_bindings.py:379,409` so the resolver is live rather than latent.
- Add eleven behavioural cases in `src/cadrumo/application/aggregation/tests/test_income_sales_invoice_evidence.py`.

## Outcome

Landed as commit `32dcf3008e` (4 files, +503 / -10).

The defect was reproduced on the real path at HEAD before any edit, and the same scenario re-run after:

```
BEFORE  casilla 01 = 1060.00   grounding = cash_fallback        withheld = 0
AFTER   casilla 01 = 1000.00   grounding = substrate_declared   withheld = 150.00
                                                                (declared_on_linked_invoice)
```

Raw counts, serial (`-n 0`): the new module 11 passed; `application/aggregation/tests` 610 passed then 635 passed with the registry income binding suite included, 7 deselected throughout; tree-wide `pytest src/cadrumo --collect-only -q` collected 20232 of 24148 with no collection errors. Lint and format clean over every touched file.

The amount guard is the load-bearing difference from the precedent it otherwise copies. The expense side asserts the cash equals the invoice `grand_total`, because an expense pays the whole contraprestacion. A sales invoice subject to retencion is paid net, so the credit is `grand_total - retention_amount`. Copying the expense form would have refused every net-paid professional invoice this path exists to ground, and dropping the retencion term would have accepted an invoice that does not describe the payment. A test pins the 1210-credit case so the guard cannot be "simplified" back.

## Notes

The `invoices` parameter on both aggregators is optional, which is a deliberate deviation from the expense side's required positional. 43 in-process call sites exist across 12 test modules, several of them peer-owned and actively being written; requiring the argument would have forced edits into live peer files for callers that hold no invoices and would pass an empty catalogue. Production is unaffected by the choice: both `*_from_repositories` entry points load the real catalogue and the single production call site passes the repository, so the evidence path is wired rather than latent. The docstring states this so the default is not later read as an oversight.

Both income entry points had to gain the repository together. The production resolver picks between the quarterly and annual aggregators by modelo, so threading one alone would have left the annual return grounding differently from the quarterly payments it reconciles against — the same asymmetry this campaign has spent its length removing. A test asserts the two paths ground one row identically.

An unresolvable invoice id is treated as no evidence rather than as an issue. The ledger surface already reports a broken link, and this pipeline's question is only whether trustworthy figures exist; raising here would report one operator fault twice under two vocabularies.

Four mutations were run against the committed shape, each applied to a copy-aside and restored: ignoring the invoice base (3 failed), copying the expense amount guard verbatim (5 failed), applying a mismatched link instead of refusing it (2 failed), and ignoring the declared retencion (1 failed). The second is the trap the brief named, and the suite catches it five times over. Restore verified post-hoc by SHA-256 match, a residue grep, and `git diff` rather than by trusting the copy step.

### Regression and correction

The first landing (`32dcf3008e`) introduced an under-declaration and was corrected by `cf7e5e315c` (4 files, +195 / -61).

All five evidence guards returned a `RentaIncomeLedgerAggregationIssue`, and returning an issue from the income classifier EXCLUDES the row. An invoice settled in two instalments -- ordinary for professional work -- therefore removed both rows and declared zero where 1060.00 of real income existed:

```
BEFORE the correction   observations: 0   issues: 2   casilla 01: 0.00
AFTER  the correction   observations: 2   issues: 0   casilla 01: 1060.00
                        refusals: partial_or_multi_transaction (x2), grounding: cash_fallback
```

That replaced an over-declaration of 60 with a 100 % under-declaration, in the sanction direction.

The guards were right; their consequence was not. This is the second time in one Step that copying the expense pipeline's shape was wrong, and the two failures share a root: the expense side and the income side are mirror images, not the same pipeline. An unevidenced gasto must NOT be claimed, so that pipeline excludes it. An unevidenced ingreso must STILL be declared, so this one degrades it. Only the checks transfer; the consequence inverts. The issue-reason enum's own docstring already stated that contract, which is why the correction restores an existing rule rather than inventing one.

The refusals now live in their own closed set, `SalesInvoiceEvidenceRefusal`, deliberately separate from the exclusion enum so the two outcome classes cannot be confused again by a future author reaching for the nearest enum. The row keeps its cash and `CASH_FALLBACK` grounding, and a new `unusable_sales_invoice_evidence` diagnostic names which check rejected the link -- without it the downgrade is invisible, since the row looks exactly like one that never had an invoice.

Enrolling that diagnostic required adding its reason to the closed `Literal` in `_source_mesh.py`. The type refused the unenrolled value at probe time, which is where that class of fault should surface; the sibling advisory learned the same lesson at calculate time by raising `ValidationError` from inside itself. The message is fitted to the same measured 512-character budget and was proved buildable at 1, 2, 3, 25 and 400 rows.

Two tests assert the income FIGURE rather than the presence of a refusal, because the regression is invisible to any test that only checks issues were raised -- which is precisely how it passed eleven green cases.

Mutation-proved: restoring the exclusion reddens 2 cases, dropping the refusal marker reddens 7, deleting a guard reddens 1. Restore verified by SHA-256 match, a residue grep and a post-hoc `git diff`.

Raw counts after the correction, serial (`-n 0`): the module 13 passed; `application/aggregation/tests` 623 passed, 7 deselected; with the registry income binding and CLI JSON conformance suites under both marker lanes, 806 passed.


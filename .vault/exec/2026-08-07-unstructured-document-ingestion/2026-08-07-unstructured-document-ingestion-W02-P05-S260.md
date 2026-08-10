---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:24e87d40bea477b06517b27274581d138df6a715c6835d6648e054e9eba59aff'
step_id: 'S260'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Read suplidos from the document — landing verified, not authored here

## Scope

- `src/cadrumo/adapters/inbound/einvoice`

## Description

This is a LANDING-VERIFICATION record, not a claim of authorship. The producer this row asks for was already at HEAD when the row was measured on 2026-08-10, landed by another lane. Attributing that lane's work to this document would be dishonest, so what follows is the evidence the row's deliverable exists, and nothing else.

- Re-read the row's premise against HEAD and find it FALSE. The row states "nothing in the package reads suplidos: zero occurrences in the e-invoice parser and zero in the on-host reading contract." That was true when the row was written and stopped being true on 2026-08-08.
- Locate the producer: `_facturae_suplidos` reads the suplidos the invoice totals state, aggregate preferred, from the Facturae `TotalReimbursableExpenses` element, with the per-line `ReimbursableExpenses` block as the fallback statement. Facturae states them twice and both statements are optional, which is why the reader prefers the aggregate rather than assuming one form.
- Confirm the fold: `_facturae_invoice_total` derives the printed total as base plus output tax plus suplidos, which is the identity the closure check tests. The commit subject names the root cause the row also names — no Facturae element equals this codebase's invoice total, so `InvoiceTotal` looks like the printed total and is not one.
- Confirm the carry to the waist: the parser's `suplidos_amount` reaches `InvoiceDraft.suplidos_amount` at the structured-reading projection, so the value the closure check consumes is populated from the document rather than left None.
- Confirm the consumer closes over it: `_total_closure_finding` checks total equals base plus cuota plus recargo plus suplido over exactly those four components.

## Outcome

The row's deliverable is at HEAD and the over-refusal it describes no longer reproduces on the Spanish national format. A Facturae specimen carrying a reimbursable expense now closes rather than raising an `ARITHMETIC_CLOSURE` finding that maps to `CLOSURE_DISCREPANCY` and BLOCKS the confirm.

The row's own control is what made it a wiring finding rather than a rule finding: with the term supplied the findings were empty even before the producer landed, so the rule was never wrong and only the producer was missing. That is why the fix is a reader and not a change to the closure identity.

**What the correction excludes, stated because a row that quietly becomes smaller is indistinguishable from one delivered in full.** The row scoped Facturae as "where it lands and why it matters", and Facturae is where it landed. It does NOT follow that the other e-invoice formats read suplidos. The row's second premise clause — "zero in the on-host reading contract" — was NOT closed by this landing: the on-host text and vision reading path still has no suplidos field in its extraction contract, so a suplido printed on a PDF or an image invoice remains unread and the same over-refusal is still reachable from those transports. The UBL and CII arms were not measured here either. What is delivered is the structured Facturae arm alone.

## Verification

Producer, fold and carry read directly from HEAD `ac219c97e8`:

    _facturae_suplidos                  einvoice/_parsers.py:608
    parsed.suplidos_amount = ...        einvoice/_parsers.py:696
    _facturae_invoice_total(..suplidos) einvoice/_parsers.py:712
    suplidos_amount=parsed.suplidos_amount   application/ledger/_evidence_draft.py:1361
    _total_closure_finding components   application/ledger/_closure_findings.py:106

Implementing commit, by another lane:

    ce26f7f6e8  2026-08-08 11:48  fix(facturae): derive the invoice total, since no Facturae element equals it

Shipped coverage found beside it, neither authored here:

    src/cadrumo/adapters/inbound/einvoice/tests/test_facturae_invoice_totals_mapping.py
      TestTheSuplidoIsReadFromEitherStatement
    src/cadrumo/application/ledger/tests/_evidence_corpus/facturae_32_retencion_suplidos_invoice.xml

Gate run requested from the single test-run authority rather than executed here.

## Notes

The row stayed open for two days after its own premise expired. That is the fifth instance this campaign has recorded of work landing under a commit whose subject names no Step, and it is the reason a row is closed on a measurement against HEAD rather than on a report.

The residual on the on-host reading contract is real remaining work and is NOT covered by this record. It belongs to the reading-contract rows in W04 P10 that own the extraction field set, and should be picked up there rather than re-opened here.

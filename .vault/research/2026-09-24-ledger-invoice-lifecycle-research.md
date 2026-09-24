---
tags:
  - '#research'
  - '#ledger-invoice-lifecycle'
date: '2026-09-24'
modified: '2026-09-24'
body_schema: 'body-v2'
body_hash: 'sha256:236f71d153b9fa81f5b5e7a1814df4acbb48b0612fdb879a0747b587c4117792'
related: []
---

# `ledger-invoice-lifecycle` research: `Invoice lifecycle domain grounding`

The distinctions the invoice and transaction lifecycle must keep, the product state behind two open correction and audit choices, and the open import-identity question (researched 2026-09-21 and 2026-09-22).

## Findings

### Lifecycle objects stay distinct

Invoice identity, economic transaction, payment or settlement, attached evidence, tax-period observation and filed declaration are separate objects even where the product links them. A payment is not necessarily a new expense, invoice plus payment must not count twice, and a missing payment record does not prove an invoice is unpaid. Gross, base, IVA, recargo, withholding, deductible allocation and net amounts are kept without encoding direction twice.

### The IVA books are richer than a cash row

AEAT's issued-invoice book records number and series, issue and distinct operation dates, the recipient and the tax breakdown, and distinguishes rectifying invoices. The received-invoice book also covers accounting and customs documents and deductible tax amounts.

### Rectification is a legal act, not an overwrite

RD 1619/2012 article 15 generally requires a new rectifying invoice that identifies the corrected invoice(s), subject to its exceptions. A local overwrite of a bookkeeping record is not that act. Invoice date, operation or accrual date, receipt or registration date, payment date and deduction period must not be collapsed, and partial business use, IVA deductibility and income-tax deductibility are not one percentage.

### Product state behind the two correction and audit choices (2026-09-22)

- Transaction IDs are derived from record content. Edit lineage records the previous ID, and reads follow it. A manual update carries `invoice_id` onto the replacement transaction but does not rewrite the invoice's `linked_transaction_ids`.
- Explicit link creation already co-commits the reciprocal transaction and invoice catalogues and the event in one secure-object batch. The combined helper takes no expected invoice revision, so an identity-changing linked edit has no revision-guarded write path.
- Invoice create and update saved the encrypted catalogue and then emitted the bucket event separately. An event failure could leave a durable invoice with no audit event, and a retry then met the duplicate-ID guard.

The options weighed and the chosen outcomes are in the correction and audit ADR.

### Open: import identity for a changed invoice

Bulk import deduplicates by the content-derived invoice ID. A changed total under the same printed number, date and counterparty creates a second catalogue record, while a renamed file with identical content is skipped. A conflict key cannot come from the printed number alone: RD 1619/2012 article 6 requires the number and, where applicable, the series, and the received-invoice book records issuer identification and the document's dates. The SII record key (issuer NIF, series-number, issue date) is outside this ledger and does not define its conflict policy. Still to decide: whether a same-identity, different-content import refuses, goes to a review queue, or coexists as a documented correction, and the exact issuer, entity, year, series and date scope, including missing data.

## Sources

- https://sede.agenciatributaria.gob.es/Sede/iva/facturacion-registro/libros-registro-iva/libro-registro-facturas-expedidas.html
- https://sede.agenciatributaria.gob.es/Sede/iva/facturacion-registro/libros-registro-iva/libro-registro-facturas-recibidas.html
- https://www.boe.es/buscar/act.php?id=BOE-A-2012-14696
- https://sede.agenciatributaria.gob.es/Sede/impuestos-tasas/iva/iva-libros-registro-iva-traves-aeat/preguntas-tecnicas-frecuentes.html

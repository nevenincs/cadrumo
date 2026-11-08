---
tags:
  - '#adr'
  - '#retenciones-workflow'
date: '2026-11-08'
modified: '2026-11-08'
body_schema: 'body-v2'
body_hash: 'sha256:fad7c4f53993b5c81d09f3f024388ed3c13b17d655e7619ec62736ff7de68f3d'
related:
  - "[[2026-09-21-retenciones-workflow-observation-payment-contract-adr]]"
  - "[[2026-09-23-retenciones-workflow-evidence-capture-scope-adr]]"
  - '[[2026-11-08-retenciones-workflow-invoice-withholding-trace-reference]]'
---

# `retenciones-workflow` adr: `The invoice is the withholding source` | (**status:** `accepted`)

Accepted 2026-11-08 by the cadrumo coordinator, on the traced causes and probe of APP-QA findings D17 and D20 (build `e621263e8c`), under the operator's standing delegation of design and tax-modelling decisions. This record amends `2026-09-21-retenciones-workflow-observation-payment-contract-adr` and `2026-09-23-retenciones-workflow-evidence-capture-scope-adr` as stated under Constraints. It reuses the invoice and movement partition of the `iva-workflow` decision that makes the invoice the IVA source.

## Problem Statement

APP-QA followed the taxpayer's path through the desktop. It imported the Libro de facturas with each invoice's retención, linked the invoices to the bank movements and set the movements' Categoría de IRPF. Modelo 130 2025 1T then showed casilla 06 at 0 instead of 900, which overpays 900. Modelo 111 and Modelo 115 refused, and the 111 refusal told the person to run CLI commands.

The causes are structural:

- Casilla 06 sums only a retención with derivation `DECLARED_ON_LINKED_INVOICE` (`src/cadrumo/domain/calculations/registry/ledger_renta_income_bindings.py:253`).
- The linked issued invoice is refused as evidence when it has no IVA category, because `decompose_invoice` reports `IVA_TREATMENT_UNDECLARED` (`src/cadrumo/application/aggregation/renta_income_evidence.py`). It is also refused when the link is recorded only on the movement side.
- The invoice-book import sets no IVA category (`src/cadrumo/application/invoices/bulk_import.py:906`).
- The 111 and 115 resolver reads only the per-perceptor store (`src/cadrumo/application/aggregation/modelo_bindings_retenciones.py:150`). Only an explicit capture fills that store, and the CLI `--received-invoice-retencion` is its sole caller. A received invoice that states a retención therefore never reaches 111 or 115.
- Capture also refuses every corporate-tax recipient (`src/cadrumo/application/aggregation/withholding_recognition.py:175`), although rent paid to an SL landlord is subject to retención.
- The desktop Retenciones tab heading is one fixed key for every modelo.

## Considerations

- The retención is an IRPF fact. The registry's IVA component catalogue (fact 0084) itself notes that whether a retención arises depends on facts the IVA category does not carry. Its role, credit or liability, is the same for every arising row of one invoice kind.
- RIRPF art. 110.3.a credits the retenciones practicadas on the activity's income. Their period follows the income's imputation (LIRPF art. 14; RIRPF arts. 7 and 79), which the existing renta income path already owns.
- RIS (RD 634/2015) art. 60.1.e subjects urban rent paid to an IS taxpayer to retención. Art. 65 makes the obligation arise at exigibility or at an earlier payment. Art. 60.1 lists no professional services, so an entity's professional fee bears no retención.
- Resident IRPF recipients of work, professional and urban-rent income are recognised PAID_OR_SATISFIED, per the payment-contract ADR.
- The `iva-workflow` invoice-source decision already partitions movements in `src/cadrumo/application/aggregation/invoice_iva_source.py`. A link counts from either side, and a paying movement is payment evidence only. One partition must serve both taxes (rule 07).

## Considered options

- Window doors that write a capture through the existing producer for each received invoice. Rejected: the person would retype facts that the invoice and its paying movement already hold, and every invoice edit would leave a stale capture.
- Infer the scheme and regime inside the CLI capture only. Rejected: the window would still have no path, and the CLI would hold a second source of the same facts.
- Project received invoices into the per-perceptor read at read time, and admit an issued invoice's stated retención whatever its IVA category. Chosen.

## Constraints

**Role and links**

- A retención's role is read from the IVA component catalogue. When the category is undeclared, the role is the one every arising row of that invoice kind shares. Code never derives the role from the kind on its own.
- An undeclared IVA category keeps blocking IVA and stops blocking IRPF.
- A link counts from either side through `with_movement_side_links`. Paying movements come from `partition_invoice_payments`, and no second partition is written.
- A cobro linked to an issued invoice is payment evidence. Its retención is the invoice's own `retention_amount`, and none is also inferred from the net movement. An unlinked net cobro keeps its own facts.

**Issued invoices**

- The stated retención is DECLARED when the invoice is the bucket's issued invoice, is linked to the receipt from either side, has a EUR value, and its cash identity settles (grand total minus retención equals the cash).
- The IRPF base and retención are then admitted even with the IVA category undeclared.
- Period imputation stays with the renta income path.

**Received invoices**

- They are projected at read time inside `load_calculation_observations`, the one read that calculation, the aggregate report and the annual summaries share. Nothing is written.
- A stored capture for the same invoice (source kind PAYABLE_INVOICE, same source object) takes precedence, and that invoice's projection is skipped.
- Income kind comes from the paying movement's registry IRPF category:
  - `arrendamiento_local` and `arrendamiento_vivienda_afecto` are urban rent.
  - Outgoing `actividad_economica` is professional.
  - A missing category, or paying movements that disagree, is a typed blocking finding naming the invoice, with a door to the movement's category.
- Recipient regime comes from the counterparty NIF form under Orden EHA/451/2008, together with the invoice's counterparty country:
  - A natural person resident in Spain is IRPF.
  - An entity form is IS.
  - A form that does not settle the regime is a typed finding.
  - A non-Spanish counterparty keeps the existing non-resident exclusion.
- Recognition:
  - IRPF recipients are recognised on the paying movement's date. An unpaid invoice stays pending and uncounted.
  - IS recipients are admitted for urban rent only, recognised at the invoice date (exigibility) or at an earlier payment.
  - An IS recipient of professional income is a blocking finding on the invoice citing RIS art. 60.1, never a 111 casilla.

**Amendments to earlier decisions**

- `2026-09-21-retenciones-workflow-observation-payment-contract-adr`: invoice-derived observations may also be projected at read time, from the invoice catalogue and its paying movements, alongside the producers' stored evidence. The store's identity, mutation and atomicity rules are unchanged.
- `2026-09-23-retenciones-workflow-evidence-capture-scope-adr`: its "RIS article 65 mapping" for IS income is enabled for urban rent only. Every other IS combination still refuses.

**Refusals and the heading**

- Refusals and findings are REFUSED with effect none. Each has a typed reason, words in all four locales and window doors. No refusal shown in a window names a CLI command.
- The Retenciones tab heading is served per modelo, as the withholding direction that the registry's form roles determine: suffered on the person's income, or practised on others. The fixed frontend key is retired.

## Implementation

We will make the invoice the withholding source in two places:

- the renta income evidence admission, for issued invoices;
- the per-perceptor read, for received invoices.

Both places reuse the link partition and the existing liability, recognition and aggregation code: `invoice_retencion_liability_defects`, `derive_withholding_recognition` and `RetencionesAggregationSourceResolver.aggregate`.

Tests use the APP-QA data in miniature through the real resolvers:

- Modelo 130 1T: casilla 06 900.00 and casilla 07 40.50.
- Modelo 111 1T, with a natural-person professional: 07 1, 08 300.00, 09 45.00.
- Modelo 115 1T: 01 1, 02 1500.00, 03 285.00.
- The refusals and the SLP finding.

## Rationale

The invoice states the retención the payer practised. Reading it from the invoice and its paying movement means the person does not enter it twice. It keeps one partition and one aggregation path, and it follows RIRPF art. 110.3.a, RIS arts. 60 and 65 and the payment-contract recognition rules.

## Consequences

- A taxpayer who keeps a Libro de facturas gets 130 casilla 06 and Modelos 111 and 115 without the CLI.
- CLI captures remain valid and take precedence over the projection.
- An SLP that withholds on its own professional fee is reported for correction.
- The APP-QA dataset changes the gestoría to a natural person, because the original 111 oracle contradicted RIS art. 60.1.

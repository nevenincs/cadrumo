---
tags:
  - '#reference'
  - '#retenciones-workflow'
date: '2026-11-08'
modified: '2026-11-08'
body_schema: 'body-v2'
body_hash: 'sha256:2c03c9618ed94dac1ed99994c5c9d7361ab63083139f58ba161539eafa545f99'
related: []
---

# `retenciones-workflow` reference: `Why invoice withholding does not reach 130, 111 and 115`

## Summary

On feature/tui at `8e9a494d8b`, an invoice's retención does not reach the withholding casillas when the taxpayer's own records hold it. This was traced for APP-QA findings D17 and D20 and confirmed with a probe through the real renta income aggregation.

## Issued invoices and Modelo 130 casilla 06

- The 130 retenciones binding sums the `declared_withheld_amount_sum` fact (`src/cadrumo/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/bindings/0001-declarations.toml:110`). `_m130_retenciones_backend_inputs` routes it to casilla 06 (`src/cadrumo/application/aggregation/modelo_bindings.py:970`).
- That fact counts only observations whose derivation is `DECLARED_ON_LINKED_INVOICE` (`src/cadrumo/domain/calculations/registry/ledger_renta_income_bindings.py:253`). The inferred derivations are reported apart from it.
- The derivation is DECLARED only when `sales_invoice_evidence_payload` admits the linked issued invoice (`src/cadrumo/application/aggregation/renta_income_evidence.py`). `_linkage_refusal` requires the movement to appear in `invoice.linked_transaction_ids`, so a link held only on the movement side is refused as `sales_invoice_link_mismatch`. `_whole_invoice_refusal` requires `decompose_invoice(invoice).is_grounded`.
- `decompose_invoice` reports `IVA_TREATMENT_UNDECLARED` for an invoice with no IVA category (`src/cadrumo/domain/invoices/decomposition.py:225`).
- The invoice-book import builds invoices without a category (`src/cadrumo/application/invoices/bulk_import.py:906`).
- Probe result for a 2000.00 base, 300.00 retención and 2120.00 cobro:

  | IVA category | Link | Result |
  |---|---|---|
  | `domestic_general` | reciprocal | 300.00 `declared_on_linked_invoice` |
  | none | reciprocal | refused `ungrounded_sales_invoice_decomposition`, 0 |
  | `domestic_general` | movement side only | refused `sales_invoice_link_mismatch`, 0 |

## Received invoices and Modelos 111 and 115

- `RetencionesAggregationSourceResolver.resolve` reads only the per-perceptor store through `load_calculation_observations` (`src/cadrumo/application/aggregation/modelo_bindings_retenciones.py:120`). When the store is empty it raises the `m111_no_retenciones_attestation_missing` or `perceptor_observations_missing` refusal.
- `build_invoice_withholding_capture` is the only translation of an invoice into that store (`src/cadrumo/application/aggregation/invoice_retencion.py:320`). Its production caller is the CLI `modelo aggregate --received-invoice-retencion`.
- `invoice_retencion_liability_defects` excludes an invoice with no IVA category (`src/cadrumo/application/aggregation/invoice_retencion.py:413`).
- `_validate_recipient` refuses every IS recipient as `corporate_income_tax_unsupported` (`src/cadrumo/application/aggregation/withholding_recognition.py:175`).
- The registry's IVA component catalogue declares the retención role per category and kind (`src/cadrumo/_data/registry/aeat/facts/0084-iva-category-component-catalogue.toml:174`):
  - every domestic issued row is `taxpayer_credit`;
  - every domestic received row is `taxpayer_liability`;
  - the catalogue's own note says that whether a retención arises depends on facts the IVA category does not carry.
- The ledger IRPF taxonomy declares the categories a movement can carry (`src/cadrumo/_data/registry/aeat/facts/0081-irpf-ledger-category-taxonomy.toml`):
  - `arrendamiento_local` and `arrendamiento_vivienda_afecto`, outgoing, for rent with retención;
  - `actividad_economica`, incoming and outgoing.

## Law read from the bundled corpus

- RIS (RD 634/2015) art. 60.1 lists the income paid to IS taxpayers that is subject to retención. Letter e is urban rent, and professional services are not listed. Art. 65 makes the obligation arise at exigibility or at an earlier payment (`src/cadrumo/_data/corpus/normatives/html/rd-634-2015.html.extracted.md`).
- LIS art. 128 places the retención obligation on payers (`src/cadrumo/_data/corpus/normatives/html/ley-27-2014.html.extracted.md`).

## Desktop heading

`desktop.modelo.credits.title` is rendered as one fixed key for every modelo (`native/desktop/frontend/src/components/modelo/workspace/CreditsView.tsx:189`).

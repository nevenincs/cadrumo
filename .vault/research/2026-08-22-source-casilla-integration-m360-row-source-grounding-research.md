---
tags:
  - '#research'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:a071799b63a02dc58b45e6aff183ffbaa087895274ae564696cd6bcfff415bc5'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# `source-casilla-integration` research: `m360 row source grounding`

Modelo 360’s official operation is an invoice-or-import-document refund-request row, within a request addressed to a refund State and period; it is not a five-value generic operation. The live worksheet carrier retains only a subset of that row and a positional synthetic identity, and no secure source owner exists for the official record. The evidence therefore favours retaining the already visible bounded deferral rather than claiming S97 enrollment; a later decision must select an owner that can retain the complete row and request context.

## Findings

### Official M360 grain is document-detail plus refund-request context

AEAT describes Modelo 360 as a request for VAT refund in another Member State (or the applicable Spanish territory for Canary Islands, Ceuta, and Melilla). Its request surface includes destination country, year and refund-period start/end. The requested refund is calculated from the operation list and records invoice and import-document counts. https://sede.agenciatributaria.gob.es/Sede/no-residentes/iva-empresarios-profesionales-no-establecidos/modelo-360-modelo-361-iva-devoluciones.html https://sede.agenciatributaria.gob.es/static_files/Sede/Procedimiento_ayuda/GZ09/360/Presentacion_formulario_360_v131115.pdf

For every operation, AEAT’s official help requires operation type (import or domestic acquisition/service), invoice and/or import-document number, document issue date, taxable base, VAT quota, deductible proportion, requested refund amount, currency, nature code (and description for “Other”), and supplier/provider identity and address; its attached-document convention further identifies invoices by issuer VAT number and invoice number. This fixes the minimum record axes that any owner must preserve. https://sede.agenciatributaria.gob.es/static_files/Sede/Procedimiento_ayuda/GZ09/360/Presentacion_formulario_360_v131115.pdf

### The existing carrier is a partial worksheet projection, not an official owner

`RefundOperationObservation` carries `member_state_code`, `operation_kind_code`, `operation_date`, `supplier_tax_id`, `refund_amount`, and `source_id`. The registry emits exactly those five business values and groups them as `per_refund_operation`; it neither carries invoice/import-document identity, taxable base, VAT quota, deductible proportion, currency, nature, supplier address/name, nor the request-period axes. `src/cadrumo/domain/calculations/registry/_detail_record_bindings.py:567` `src/cadrumo/_data/registry/aeat/modelos/360/revisions/2010-y-siguientes/bindings/0001-refund-operation-row-bindings.toml:1`

The worksheet assembler manufactures `detalle:per_refund_operation:row-{row_index}` and defaults a missing date to the filing year’s final day. The resolver subsequently sorts by member State, date, and supplier id. Neither construction is a durable official document identity, so row order cannot become the source authority or safely distinguish documents with the same exposed fields. `src/cadrumo/application/calculations/_row_set_assembly.py:824` `src/cadrumo/domain/calculations/registry/_detail_record_bindings.py:636`

### Existing architecture supports an explicit refusal, not enrollment

The source mesh classifies `REFUND_OPERATION` as deferred, and the census accurately names the absence of a durable repository and live calculation resolver. No live owner can therefore make the required secure and stable document identity claim. `src/cadrumo/application/aggregation/_source_mesh.py:290` `src/cadrumo/_data/source_connectivity/census.toml:239`

The available alternatives are: enroll the partial worksheet carrier, rejected because it loses official axes and manufactures identity; or retain a bounded ingress-blocked row, favoured by the evidence until a single secure owner preserves request context, every official document axis, immutable document identity, and content fingerprint. S97 must then prove real resolver ownership and collision/refusal semantics; S98 must prove encrypted revision persistence/replay plus diagnostics, review, and only a supported official repeated-record export; S99 may claim `connected` only after that evidence and independent review. This research does not adjudicate a new carrier or storage design.

## Sources

- https://sede.agenciatributaria.gob.es/Sede/no-residentes/iva-empresarios-profesionales-no-establecidos/modelo-360-modelo-361-iva-devoluciones.html
- https://sede.agenciatributaria.gob.es/static_files/Sede/Procedimiento_ayuda/GZ09/360/Presentacion_formulario_360_v131115.pdf
- `src/cadrumo/domain/calculations/registry/_detail_record_bindings.py:567`
- `src/cadrumo/domain/calculations/registry/_detail_record_bindings.py:636`
- `src/cadrumo/application/calculations/_row_set_assembly.py:824`
- `src/cadrumo/application/aggregation/_source_mesh.py:290`
- `src/cadrumo/_data/registry/aeat/modelos/360/revisions/2010-y-siguientes/bindings/0001-refund-operation-row-bindings.toml:1`
- `src/cadrumo/_data/source_connectivity/census.toml:239`

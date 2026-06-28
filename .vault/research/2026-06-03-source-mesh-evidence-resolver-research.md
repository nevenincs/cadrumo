---
tags:
  - '#research'
  - '#source-mesh-evidence-resolver'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-05-20-calculation-source-connectivity-adr]]"
---

# `source-mesh-evidence-resolver` research: `S26 PurchaseInvoiceEvidenceSourceResolver design + data-shape blocker`

Subagent ground-truth pass for #635 W02.P05.S26 (Adapt purchase
invoice evidence records into source mesh resolution).

## Proposed resolver shape

The subagent's analysis follows the existing
`InvoiceCatalogueSourceResolver` template at
`src/aeat/application/invoices/_source_resolver.py`. The intended
landing path:

- New file `src/aeat/application/ledger/_evidence_source_resolver.py`
  (sibling to `_evidence.py`, not inside it — `_evidence.py` is
  service-CRUD and peer-WIP frequently).
- Class `PurchaseInvoiceEvidenceSourceResolver` with
  `resolver_id = "purchase_invoice_evidence"`,
  `owned_sources = ("purchase_invoice_evidence",)`.
- Constructor accepts optional `evidence_service:
  PurchaseInvoiceEvidenceService` for test injection; defaults to
  the real service.
- `resolve(context)` flow: pre-filter on
  `_revision_has_binding_source(context.revision,
  "purchase_invoice_evidence")`; load records via
  `evidence_service.list_all(bucket_id=context.bucket_id)`; filter
  by `invoice_date` parsed against `(filing_year, period)`; project
  each record to an `InvoiceObservation`; call
  `resolve_invoice_binding_values(context.revision, observations)`;
  emit per-record provenance with `fingerprint =
  f"sha256:{record.source_sha256}"` (leverages already-persisted
  SHA-256, satisfies ADR Phase-9 resolver-fingerprint contract).

## Data-shape blocker

`PurchaseInvoiceEvidence` (defined at
`src/aeat/application/ledger/_evidence.py:67`) carries
`evidence_id`, `bucket_id`, `source_path`, `source_sha256`,
`media_kind`, `supplier?`, `invoice_number?`, `invoice_date?`,
`taxable_base?`, `iva_rate?`, `iva_amount?`, `notes`,
`created_at`, `updated_at`.

`InvoiceObservation` (at
`src/aeat/domain/calculations/registry/...`) requires
`invoice_id`, `party_tax_id`, `country_code`, `transaction_date`,
`base_amount`, `intracommunity_clave`, `party_legal_name`.

**Missing fields on `PurchaseInvoiceEvidence`**:

- `party_tax_id` — counterparty NIF / EORI. Not authored on the
  evidence record because evidence today captures only the
  document-image side (OCR extraction is downstream).
- `country_code` — counterparty residence country. Same reason.
- `intracommunity_clave` — required by `InvoiceObservation` (T / E
  / A). The resolver's `_intracommunity_clave` helper from
  `InvoiceCatalogueSourceResolver` derives clave from
  `IvaCategory`, but `PurchaseInvoiceEvidence` has no IVA category
  axis.

Consequence: a resolver authored against the current
`PurchaseInvoiceEvidence` shape would skip-and-diagnose EVERY
record (no record satisfies `_invoice_observation`'s required
axes). Shipping that resolver would be near-pure infrastructure
with zero contribution to binding values until the evidence schema
extends.

## Recommended split

Two follow-up Steps, neither this one:

### Step a — Evidence schema extension (precondition)

Extend `PurchaseInvoiceEvidence` with `counterparty_tax_id?`,
`counterparty_country?`, `iva_category?` fields. These come from
the OCR / operator-edit pipeline once invoice metadata is
extracted; today the evidence record is image-only. The schema
extension MUST land via the roundtrip-discipline (anti-tautology
+ real-backend test) per `aeat-roundtrip-discipline`.

### Step b — S26 resolver (deferred until Step a lands)

Authoring per the subagent's proposal once the data is available.

## Alternative: ship the resolver as a forward-investment

If forward investment is acceptable (the resolver is wired and
returns empty resolutions today, populates as the evidence schema
grows), the commit is:

- new module `_evidence_source_resolver.py` per the subagent's
  outline
- 5 service-contract tests including an explicit
  `test_resolver_returns_empty_today_due_to_evidence_axes_gap`
  documenting the current limitation
- registry of the resolver in the source-mesh wire-up

This option ships infrastructure that is operationally inert until
the evidence schema extends. Per `aeat-source-hygiene` ("Do not
land design-only implementation shells. Ship working behavior,
executable validation, and useful tests together"), the
forward-investment option arguably violates the rule.

## Recommendation

Defer S26 until the evidence schema extends. Author Step a (schema
extension) as a new plan row under #635 W02 — it is the actual
blocker, and naming it as a Step makes its priority explicit. Then
land S26 against the extended schema.

## Source

Subagent ground-truth discovery 2026-06-03 against #635 W02.P05.S26.
Cited file:line evidence:
- `src/aeat/application/ledger/_evidence.py:67` (PurchaseInvoiceEvidence)
- `src/aeat/application/invoices/_source_resolver.py` (template)
- `src/aeat/application/aggregation/_source_mesh.py:87,265,338`
- `src/aeat/application/aggregation/_modelo_bindings.py:47,50,141,428`
- `src/aeat/domain/calculations/registry/_bindings.py:3006`
  (PurchaseInvoiceEvidence already mapped to `_InvoiceSelector`)

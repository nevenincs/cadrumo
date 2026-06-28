---
tags:
  - "#research"
  - "#invoice-catalogue"
date: "2026-04-17"
modified: '2026-04-17'
related:
  - "[[2026-04-14-transaction-catalogue-research]]"
  - "[[2026-04-14-transaction-catalogue-adr]]"
  - "[[2026-04-13-p2a-financial-provider-adr]]"
  - "[[2026-04-13-p2e-tax-category-catalogue-adr]]"
---

# `invoice-catalogue` research: `tdp-t3-enrich-invoice-surface`

Grounds issue `#75` (P2-C). Delivers the typed invoice catalogue for issued
and received invoices with a many-to-one link from T1/T2 transactions to an
invoice. Sits inside the TDP T3-Enrich step defined in `#104` and depends on
the upstream T1 `RawTransaction` and T2 `Transaction` catalogues that were
already landed by `#73` and `#74` on `main`.

## Findings

### Upstream contracts already on main

- `aeat.domain.financial.RawTransaction` and `aeat.domain.financial.providers.RawTransaction`
  are the T1 public boundary; already strict, frozen, provenance-rich.
- `aeat.domain.financial.transactions.TransactionCatalogue` is the T1/T2 wrapper
  landed by `#74`. It stores `invoice_id: str | None` as a foreign-key slot
  and exposes `link_invoice(catalogue, transaction_id, invoice_id)` to mutate
  that slot via an immutable-return helper.
- The transaction catalogue already imposes the provenance invariant: every
  downstream structure must preserve the chain back to its T1 source.

### Many-to-one linking semantics

- Issue `#75` explicitly allows an invoice to be referenced by *many*
  transactions (deposit + later refund), while each transaction may reference
  *at most one* invoice.
- The live shape of the transaction catalogue enforces the "at-most-one"
  direction; the invoice catalogue must enforce the "many" direction via
  `Invoice.linked_transaction_ids: tuple[str, ...]`.
- Linking must be bidirectional by design: `link_transaction(invoice_id,
  transaction_id)` should update the invoice side **and** call the existing
  `aeat.domain.financial.transactions.link_invoice` on the transaction catalogue so
  the two catalogues never drift.

### IVA totals invariants

- Each `InvoiceLine` carries `subtotal`, `iva_rate`, and `iva_amount`.
- The invoice body's `base_total`, `iva_total`, and `grand_total` MUST equal
  the sum of the per-line `subtotal`, per-line `iva_amount`, and the sum of
  those two respectively. A rounded Decimal comparison with a small tolerance
  (1 cent) is appropriate so line-level rounding does not reject legitimate
  AEAT-compliant invoices, but the implementation should be stricter when
  possible.
- Lines bearing `EXEMPT` or `NOT_SUBJECT` IVA rates must carry
  `iva_amount == 0`. Numeric IVA rates (`RATE_0`, `RATE_4`, `RATE_10`,
  `RATE_21`) must match the per-line product `subtotal * rate` within a
  1-cent tolerance. The enum must encode the rate percentage so the check is
  deterministic and not a string lookup.
- For exempt invoices the invoice-level `iva_total` is `0`; `grand_total`
  therefore equals `base_total` for exempt invoices.

### Counterparty identity (NIF / CIF / VAT number)

- The issue mandates `counterparty_tax_id` validation. Spanish tax IDs have
  three shapes:
  - NIF (natural person): 8 digits + 1 checksum letter (e.g. `12345678Z`).
  - NIE (non-resident individual): leading `X`/`Y`/`Z` + 7 digits + letter.
  - CIF (legal entity): leading letter (A-W minus some) + 7 digits +
    control (digit or letter).
- EU VAT numbers are prefixed with an ISO-2 country code (`ES`, `DE`, `FR`,
  etc) followed by the national identifier.
- `counterparty_country` is an ISO-3166 alpha-2 code; when country is `ES`,
  the `counterparty_tax_id` MUST pass Spanish-NIF/NIE/CIF validation. When
  country is non-ES, the `counterparty_tax_id` is accepted as a VAT number
  in the appropriate format (we enforce the ISO prefix matches when present
  but do not fully validate every member-state format).
- Implementation: a standalone `_validators.py` module hosting
  `validate_spanish_tax_id`, `validate_vat_number`, and
  `validate_country_code` helpers, all raising standard `ValueError` so
  pydantic surfaces them as validation errors.

### Storage

- Repo precedent for immutable catalogues is one JSON file per catalogue,
  loaded via `model_validate_json` and written with
  `model_dump_json(indent=2)` through an atomic `os.replace` temp-file swap
  (see `aeat.domain.financial.transactions._service`).
- Apply the same pattern under `AEAT_INVOICES_DIR` with a default filename
  `invoices.json`.
- The catalogue must reject duplicate `invoice_id` values when constructed
  from an iterable, exactly like `TransactionCatalogue` does today.

### Stable invoice ID

- Issue text specifies `invoice_id: str  # stable hash`.
- Deterministic hash over
  `(kind, invoice_number, issued_at.isoformat(), counterparty_tax_id,
  currency, grand_total)` is sufficient to uniquely identify one invoice
  instance: AEAT requires invoice numbers to be unique per issuer per year
  but two parties could each have "INV-001" — binding the tax ID disambiguates.
- Use lowercase SHA-256 hex digest, consistent with
  `derive_transaction_id` in `_models.py`.

### Reconciliation heuristic (`aeat invoices reconcile`)

- The issue asks for an auto-suggest of links by amount + counterparty.
- Scope: find unlinked invoices and unlinked transactions in the configured
  stores; for each unlinked invoice, search the transaction catalogue for
  unlinked transactions whose `raw.amount` matches `±grand_total` within a
  small tolerance AND whose `raw.counterparty` matches the invoice's
  `counterparty_name` via case-insensitive substring match. Emit suggestions
  only — never auto-apply. This keeps the behaviour deterministic and safe.
- Sign convention: an ISSUED invoice is income → match a positive incoming
  transaction amount. A RECEIVED invoice is an expense → match a negative
  outgoing amount. Validate this directionality in the reconciler.

### CLI integration

- `aeat financial` already hosts `ingest` (T1) and `txs` (T2).
- The issue body uses the top-level root `aeat invoices …` but project
  precedent for financial-pipeline CLIs (as landed by #73/#74) is nesting
  them under `aeat financial`. The invoice commands should therefore live
  under `aeat financial invoices …` as a nested Typer app; this matches the
  T1/T2 placement and keeps the root CLI lean. We'll document this
  placement in the ADR and note the deviation from the issue-body wording
  explicitly.

### Settings discipline

- `Settings` in `src/aeat/config.py` is the single source of truth and
  `tests/test_config.py` enforces 1:1 alignment with `env/.env.example`.
- Add `aeat_invoices_dir: Path` defaulting to
  `PROJECT_ROOT / "var" / "financial" / "invoices"` and mirror the entry
  in `env/.env.example` in the same change.

### Sibling-branch boundary constraints

- `src/aeat/domain/financial/categories/` already exists on `main` and is the
  spending-category catalogue, NOT the future tax-category catalogue from
  issue `#77`. The invoice package must not couple to it.
- Attachment service `#76` is not yet on main; typing stubs only.
- Tax category `#77` is not yet on main; typing stubs only. Runtime fields
  on `InvoiceLine` remain `category_id: str | None` strings.

### Verification strategy

- Colocated unit tests under `src/aeat/domain/financial/invoices/` match repo style.
- Each `@pytest.mark.unit` test must cover: IVA line totals, invoice totals
  round-trip, duplicate-invoice rejection, NIF/CIF/VAT validation, linking
  semantics (many-to-one, bidirectional with transactions), reconciliation
  heuristic positive + negative cases, JSON round-trip, CLI smoke paths
  for `list`, `show`, `link`, `reconcile`.
- No mocks, no patches, no stubs — only real local fixtures built from
  in-repo types.

## Design decisions needing ADR

1. Canonical `invoice_id` hash input + algorithm.
2. `IvaRate` enum shape (StrEnum with numeric payloads vs. named payloads).
3. Many-to-one linking semantics and bidirectional update contract.
4. Tax-ID validator surface and strictness by country.
5. CLI placement (`aeat financial invoices` vs `aeat invoices`).
6. Reconciliation matching tolerance + heuristic specification.
7. Storage filename and atomic-write pattern (follow `#74` precedent).

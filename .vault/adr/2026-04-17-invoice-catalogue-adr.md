---
tags:
  - "#adr"
  - "#invoice-catalogue"
date: "2026-04-17"
modified: '2026-04-17'
related:
  - "[[2026-04-17-invoice-catalogue-research]]"
  - "[[2026-04-14-transaction-catalogue-adr]]"
  - "[[2026-04-13-p2a-financial-provider-adr]]"
---

# `invoice-catalogue` adr: `immutable-invoice-catalogue-and-bidirectional-linking` | (**status:** `accepted`)

## Problem Statement

Issue `#75` must introduce a durable invoice catalogue for issued (income)
and received (expense) invoices, with a many-to-one link from
`aeat.domain.financial.transactions.Transaction` (T1/T2) to `Invoice` (T3). One
invoice may be cited from multiple transactions (e.g. deposit + refund);
one transaction may cite at most one invoice. The catalogue must enforce
IVA totals, validate NIF/CIF/VAT counterparty identities, preserve T1
provenance indirectly through its transaction links, and ship a usable
CLI without coupling to sibling packages still in flight (`#76` attachment
service, `#77` tax-category catalogue).

## Considerations

- `RawTransaction` (T1) and `TransactionCatalogue` (T2) are already on `main`
  and expose the seams this package must plug into.
  `TransactionCatalogue` already carries `invoice_id: str | None` and an
  immutable-return `link_invoice` helper.
- The existing transaction catalogue enforces one-invoice-per-transaction;
  the invoice side must enforce many-transactions-per-invoice.
- AEAT invoice identity is not globally unique on `invoice_number` alone:
  two issuers can both number invoices `INV-001`. Identity must incorporate
  the counterparty tax ID and issue date.
- IVA totals are tax-law invariants: if the invoice totals do not match the
  line totals, the invoice is wrong. Validation must be strict but tolerant
  to 1-cent rounding at the line-item level.
- Spanish tax ID validation (NIF / NIE / CIF) is a well-defined checksum
  scheme and MUST be enforced for `counterparty_country == "ES"`. Non-ES
  counterparties use national VAT number formats that are impractical to
  fully validate here; we enforce the ISO-2 country prefix when present.
- Sibling branches for attachments (`#76`) and tax categories (`#77`) are
  not yet merged to main. Runtime fields must be plain strings; typing
  can be strengthened via internal `Protocol` placeholders.

## Constraints

- Public API must be imported from `aeat.domain.financial.invoices` only.
- Every persisted structure must be strict pydantic v2; closed sets must
  use `enum.StrEnum`.
- Errors inherit from `aeat.core.errors.AeatError`; logging goes through
  `aeat.core.logging.get_logger(__name__)`.
- `Invoice`, `InvoiceLine`, and `InvoiceCatalogue` are frozen models with
  immutable-return helpers. No in-place mutation.
- `tests/test_config.py` enforces `Settings` ↔ `env/.env.example`
  alignment: the new setting must be added in both places.

## Implementation

### Package shape

- Create `src/aeat/domain/financial/invoices/` following the `#74` precedent:
  - `__init__.py` — public re-exports only.
  - `_enums.py` — `InvoiceKind`, `IvaRate`, `PaymentStatus`.
  - `_errors.py` — `InvoiceError`, `InvoiceCatalogueError`,
    `InvoicePersistenceError`, `InvoiceNotFoundError`,
    `InvoiceLinkError`.
  - `_validators.py` — `validate_spanish_tax_id`,
    `validate_vat_number`, `validate_country_code`, all raising
    `ValueError` with stable messages so pydantic surfaces them as
    validation errors.
    - `validate_spanish_tax_id(value)` implements AEAT's canonical
      algorithm:
      - **NIF** (natural person): 8 digits followed by 1 letter; letter
        equals `"TRWAGMYFPDXBNJZSQVHLCKE"[number % 23]`.
      - **NIE**: leading `X`/`Y`/`Z` substituted with `0`/`1`/`2` to
        form an 8-digit number, then the NIF letter check is applied.
      - **CIF** (legal entity): leading letter from
        `"ABCDEFGHJKLMNPQRSUVW"` followed by 7 digits and a 1-char
        control. Control is computed as the Luhn-like sum over the 7
        digits; digits in positions {0,2,4,6} (1-indexed odd) are
        doubled and cross-summed. Leading letters `"KPQRSNW"` require a
        **letter control** taken from `"JABCDEFGHI"[(10 - sum) % 10]`;
        leading letters `"ABEH"` accept either control form (both
        historically in circulation). All other leading letters accept
        either form too per the official AEAT reference.
    - `validate_vat_number(value, country)` is used for non-`ES`
      counterparties: the value MUST begin with the `country` ISO-2
      prefix uppercased, followed by 4–20 alphanumeric characters.
      Further per-country checksum validation is out of scope.
    - `validate_country_code(value)` accepts any 2-character ISO-3166
      alpha-2 alphabetic code, uppercased.
  - `_models.py` — `Invoice`, `InvoiceLine`, `InvoiceCatalogue`,
    `derive_invoice_id`.
  - `_service.py` — `load_invoices`, `save_invoices`, `find_invoice`,
    `link_transaction`, `find_unmatched`, `suggest_reconciliations`.
  - `_stubs.py` — `Protocol` placeholders for future attachment / tax
    category runtime types.
  - `test_validators.py`, `test_models.py`, `test_catalogue.py`,
    `test_reconciliation.py`, `test_cli.py`.

### Enums

```python
class InvoiceKind(StrEnum):
    ISSUED = "ISSUED"
    RECEIVED = "RECEIVED"

class IvaRate(StrEnum):
    RATE_0 = "RATE_0"
    RATE_4 = "RATE_4"
    RATE_10 = "RATE_10"
    RATE_21 = "RATE_21"
    EXEMPT = "EXEMPT"
    NOT_SUBJECT = "NOT_SUBJECT"

class PaymentStatus(StrEnum):
    PAID = "PAID"
    PENDING = "PENDING"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    OVERDUE = "OVERDUE"
    CANCELLED = "CANCELLED"
```

A private `_IVA_RATE_PERCENTAGES: Mapping[IvaRate, Decimal | None]` maps
each numeric rate to its percentage (`Decimal("0.21")` etc). `EXEMPT`
and `NOT_SUBJECT` map to `None` to signal "no numeric relation to
subtotal."

### Models

- `InvoiceLine` fields: `description: str`, `quantity: Decimal`,
  `unit_price: Decimal`, `subtotal: Decimal`, `iva_rate: IvaRate`,
  `iva_amount: Decimal`, `category_id: str | None`.
  Validators enforce (**line-level** tolerance `Decimal("0.01")`):
    - `quantity > 0`, `unit_price >= 0`, `subtotal >= 0`,
      `iva_amount >= 0`.
    - `abs(subtotal - quantity * unit_price) <= Decimal("0.01")`.
    - If `iva_rate is EXEMPT or NOT_SUBJECT` → `iva_amount == 0` exactly.
    - If `iva_rate` is numeric → `abs(iva_amount - subtotal *
      _IVA_RATE_PERCENTAGES[iva_rate]) <= Decimal("0.01")`.
    - `description` trimmed non-empty.
    - `category_id` trimmed; blank is rejected but `None` allowed.

- `Invoice` fields: `invoice_id: str` (64-char hex),
  `kind: InvoiceKind`, `invoice_number: str`, `issued_at: date`,
  `counterparty_name: str`, `counterparty_tax_id: str`,
  `counterparty_country: str` (ISO 3166 alpha-2),
  `base_total: Decimal`, `iva_total: Decimal`, `grand_total: Decimal`,
  `currency: str` (ISO 4217), `lines: tuple[InvoiceLine, ...]`,
  `payment_status: PaymentStatus`,
  `linked_transaction_ids: tuple[str, ...]` (deduplicated, frozen),
  `notes: str`.
  Validators enforce (**invoice-level tolerances are EXACT** to prevent
  per-line-tolerance accumulation from drifting invoice totals):
    - All totals non-negative.
    - `lines` non-empty.
    - `base_total == sum(line.subtotal for line in lines)` exactly.
    - `iva_total == sum(line.iva_amount for line in lines)` exactly.
    - `grand_total == base_total + iva_total` exactly.
    - For invoices where every line is `EXEMPT`/`NOT_SUBJECT`,
      `iva_total == 0` exactly and `grand_total == base_total` exactly
      (this falls out of the rules above but is asserted explicitly to
      make the intent visible).
    - `counterparty_country` normalized to uppercase and matched against
      `validate_country_code` (ISO-3166 alpha-2).
    - `counterparty_tax_id` validated via
      `validate_spanish_tax_id` when country is `ES`; otherwise
      `validate_vat_number(value, counterparty_country)`.
    - `currency` normalized to uppercase ISO-4217.
    - `linked_transaction_ids` deduplicated while preserving first-seen
      order; each entry must be a 64-char lowercase hex transaction ID
      (matches the `#74` hash shape), blank rejected.
    - `invoice_id` is derived via
      `derive_invoice_id(...)` in a `model_validator(mode="before")`
      hook. The before-hook coerces `kind`, `issued_at`,
      `counterparty_tax_id`, `currency`, and `grand_total` into the
      canonical types used for hashing (strings and `Decimal`) without
      running the later field / line validators (those run after). If
      the caller supplied an `invoice_id` it must equal the derived
      digest exactly; otherwise the derived digest is assigned.
    - `notes` trimmed; empty string allowed.

- `derive_invoice_id(...)` computes
  `sha256(json({kind, invoice_number, issued_at_iso, counterparty_tax_id,
  currency, grand_total_canonical}))` with canonical, stable JSON
  serialization consistent with `derive_transaction_id` style.

- `InvoiceCatalogue` mirrors `TransactionCatalogue`:
  `invoices: Mapping[str, Invoice]`, accepts a mapping or iterable,
  rejects duplicate `invoice_id` on iterable construction, freezes the
  mapping, exposes `__iter__ / __len__ / __contains__ / get / values /
  from_invoices`.

### Service layer

- `load_invoices(path)` / `save_invoices(catalogue, path)` use the same
  atomic temp-file replacement as `_service.py` in `#74`.
- `find_invoice(catalogue, invoice_id) -> Invoice | None`.
- `link_transaction(catalogue, invoice_id, transaction_id)
  -> InvoiceCatalogue`:
    - Looks up the invoice, raising `InvoiceNotFoundError` if absent.
    - Validates the transaction ID shape (64-char lowercase hex).
    - Idempotent: if `transaction_id` is already present in
      `linked_transaction_ids`, returns a new catalogue whose invoice
      is re-validated but value-equal to the original (no duplicate
      tuple entry).
    - Otherwise returns a new immutable catalogue with the transaction
      ID appended to `linked_transaction_ids`.
- `find_unmatched(catalogue, *, kind: InvoiceKind | None = None) ->
  tuple[Invoice, ...]` — returns invoices with an empty
  `linked_transaction_ids` tuple, optionally filtered by kind.
- `suggest_reconciliations(invoices, transactions, *, amount_tolerance
  = Decimal("0.01")) -> tuple[ReconciliationSuggestion, ...]`:
    - `ReconciliationSuggestion` is a strict frozen pydantic model with
      `invoice_id`, `transaction_id`, `amount_match: bool`,
      `counterparty_match: bool`, `score: Decimal`.
    - Only considers unlinked invoices (empty
      `linked_transaction_ids`) and transactions whose `invoice_id` is
      `None`.
    - Matches on sign-aware amount: ISSUED invoices → transactions with
      `raw.amount ≈ +grand_total`; RECEIVED → `raw.amount ≈ -grand_total`.
      "≈" means `abs(raw.amount - expected) <= amount_tolerance`.
    - Counterparty similarity: case-insensitive whitespace-trimmed
      substring match between `invoice.counterparty_name` and
      `transaction.raw.counterparty`. When `transaction.raw.counterparty`
      is `None`, counterparty_match is `False`.
    - **Score**: `Decimal("0.5") * int(amount_match) + Decimal("0.5") *
      int(counterparty_match)`, range `[0, 1]`. Only suggestions with
      `amount_match is True` are emitted; a pure-counterparty hint
      would produce too many false positives for a safe auto-suggest.
    - Results are sorted by score descending, then by
      `(invoice_id, transaction_id)` ascending for determinism.
    - Emits suggestions only; does not apply them. The caller decides
      whether to call `link_transaction` + `link_invoice` together.

### Bidirectional linking contract

The two catalogues are loosely coupled: `Invoice.linked_transaction_ids`
lives in `aeat.domain.financial.invoices`, `Transaction.invoice_id` lives in
`aeat.domain.financial.transactions`. We acknowledge that two sequential
`os.replace` writes are **not** truly atomic — the classical all-or-nothing
guarantee requires either a shared single-file snapshot or a write-ahead
journal. We explicitly defer journalling until the Track-B persistence
layer lands (`#81` / post-`P2-K`), and instead adopt the following
rigorous contract that is safe for single-operator use:

- A single helper
  `aeat.domain.financial.invoices.link_transaction_bidirectional(invoices_path,
  transactions_path, invoice_id, transaction_id)` performs the update:
  1. Loads both catalogues.
  2. Computes both new catalogues in memory and validates each by
     re-instantiating the pydantic model.
  3. Writes the **invoice catalogue first** via the existing atomic
     temp-file + `os.replace` pattern.
  4. Writes the **transaction catalogue second** via the same pattern.
  5. If step 4 fails, attempts to restore the original invoice
     catalogue via the same atomic pattern (the pre-update in-memory
     copy is always retained). If the restore itself fails, raises
     `InvoiceLinkInconsistencyError` carrying both file paths and the
     IDs involved — the operator is expected to resolve manually.
- A verify helper
  `aeat.domain.financial.invoices.verify_link_consistency(invoices,
  transactions) -> tuple[LinkInconsistency, ...]` returns a list of
  pairs where the two catalogues disagree (invoice cites tx but tx
  does not cite invoice, or vice versa). The CLI exposes this via
  `aeat financial invoices verify`.
- Loading and returning catalogues never attempts to auto-heal. The
  in-memory contract is single-direction by design; the CLI is the
  only layer that enforces the cross-catalogue invariant.

This is weaker than full atomicity by design but stronger than
best-effort: every failure mode is named, is typed, and produces
output the operator can act on. #104 T3 invariant is satisfied because
the chain remains `invoice → tx → raw` via
`linked_transaction_ids` — provenance is never lost, at most it is
temporarily duplicated across halves.

### CLI integration

The primary placement nests under the existing `aeat financial` Typer
app (matching `ingest` from `#73` and `txs` from `#74`). To honour the
exact wording of the issue body (`aeat invoices list|show|link|
reconcile`), we **additionally** register the same Typer app as a
top-level `aeat invoices` alias — both paths run the same commands.
This keeps the in-repo precedent for financial-pipeline CLIs while
preserving the user-visible surface described in the issue.

- Primary path:
  - `aeat financial invoices list [--kind issued|received]`
  - `aeat financial invoices show <invoice-id>`
  - `aeat financial invoices link <invoice-id> <tx-id>`
  - `aeat financial invoices reconcile [--apply]`
  - `aeat financial invoices verify`
- Top-level alias (same commands):
  - `aeat invoices list …` etc.
- `reconcile` prints the suggestion table; `--apply` executes each
  high-confidence suggestion via
  `link_transaction_bidirectional`, skipping those that would produce
  an `InvoiceNotFoundError` or transaction not-found.
- `verify` prints any inconsistencies detected by
  `verify_link_consistency` and exits with code `2` when any are found.

### Settings

- Add `aeat_invoices_dir: Path = PROJECT_ROOT / "var" / "financial" /
  "invoices"` to `Settings`. Mirror in `env/.env.example`:
  `AEAT_INVOICES_DIR=var/financial/invoices`.
- Catalogue file is `invoices.json` inside the configured directory.

## Rationale

- Mirroring the `#74` package shape minimises cognitive load and keeps
  the Track B codebase uniformly reviewable.
- Deterministic `invoice_id` over the tax-ID + invoice-number + date +
  currency + total tuple is the narrowest input set that guarantees
  uniqueness without tying identity to transient fields like
  `notes` or `payment_status` that change over an invoice lifecycle.
- Strict IVA arithmetic validation catches data-quality issues at
  the catalogue boundary rather than later in classification (T4) or
  handoff (T6), where they would be far more expensive to diagnose.
- Bidirectional linking is a CLI-level concern, not a model-level one,
  because the two catalogues live in separate files with separate
  persistence. Keeping the model-level helpers unilateral keeps them
  simple; the CLI enforces the cross-catalogue invariant.
- Reconciliation is strictly suggest-only by default; amount-matching
  without human confirmation is explicitly not automatic. Autonomy is
  gated behind an explicit `--apply` flag.

### Provenance invariant

Unlike the `#74` `Transaction` wrapper, which embeds `RawTransaction`
verbatim, `Invoice` records do not embed their source document. The
T1 provenance chain is preserved **indirectly** via
`linked_transaction_ids`: every classified transaction that cites an
invoice still carries its own `raw` provenance back to T1, and the
invoice→transaction→raw chain satisfies the #104 T3 invariant
("every enrichment carries a citation chain to its source document").
This is a conscious relaxation vs. #74's direct embed, made because
invoices arrive from heterogeneous sources (PDFs via `#76`, Gmail via
`#80`, manual entry) whose raw byte representations are too large and
too varied to embed in every catalogue record. The attachment service
(`#76`) will fill in the byte-level provenance when it lands.

### Schema versioning

The catalogue file stores no schema-version field in this PR. Schema
migration is explicitly deferred to the broader Track-B persistence
story (`P2-K` / `#81`). Breaking changes to `Invoice` / `InvoiceLine`
in the interim will require operators to regenerate the catalogue
file. This mirrors the stance taken by `#74`.

### Known IVA rate gaps

`IvaRate` captures the five canonical Spanish rates in force for 2026
(`RATE_0`, `RATE_4`, `RATE_10`, `RATE_21`) plus `EXEMPT` and
`NOT_SUBJECT`. The transient `RATE_5` used in 2022-2024 Spanish energy
/ food regulations is **intentionally omitted** — its window is closed
and a historical-rate enum would expand every VAT downstream consumer.
If a future issue ingests pre-2025 data, the enum can be extended.

## Consequences

- The invoice catalogue depends hard on the T1 and T2 shapes already on
  `main`. Changes to `RawTransaction` or `Transaction` would ripple into
  `suggest_reconciliations` and the CLI wiring.
- Attachment (`#76`) and tax-category (`#77`) dependencies remain
  soft — typing-only placeholders keep the interface described but
  non-binding at runtime.
- A future bulk re-tally or IVA re-computation can be layered on top of
  `Invoice` without touching the storage shape; all totals are already
  stored verbatim so the provenance of computed values is preserved.
- The catalogue does not implement currency conversion. Multi-currency
  invoices remain supported (field `currency` is free-form ISO 4217) but
  cross-currency linking is delegated to `#103` (FX tracking).
- The sign-aware reconciliation heuristic is simple by design and will
  miss split-payment cases (one invoice paid by many transactions where
  no single transaction amount equals the grand total). That edge case
  is intentionally out-of-scope for this PR and will be revisited when
  the LLM-driven matching engine (`#89`) lands.

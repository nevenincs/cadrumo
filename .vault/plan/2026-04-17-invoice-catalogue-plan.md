---
tags:
  - "#plan"
  - "#invoice-catalogue"
date: "2026-04-17"
modified: '2026-04-17'
related:
  - "[[2026-04-17-invoice-catalogue-adr]]"
  - "[[2026-04-17-invoice-catalogue-research]]"
  - "[[2026-04-14-transaction-catalogue-adr]]"
---

# `invoice-catalogue` plan: `p2-c-invoice-catalogue-and-linking`

Implements `[[2026-04-17-invoice-catalogue-adr]]` for issue `#75`
(Track B, TDP step T3-Enrich).

## Preconditions

- Branch: `feature/75-invoice-catalogue` already rebased onto
  `origin/main` (completed).
- Upstream on main: `aeat.domain.financial.RawTransaction` (#73),
  `aeat.domain.financial.transactions.TransactionCatalogue` (#74).

## Phase 1 — Package skeleton + settings

1. Add setting `aeat_invoices_dir: Path` to
   `src/aeat/config.py`. Default
   `PROJECT_ROOT / "var" / "financial" / "invoices"`. Alphabetise in
   the Financial ingest block alongside `aeat_financial_txs_dir`.
2. Add corresponding line in `env/.env.example`:
   `AEAT_INVOICES_DIR=var/financial/invoices`.
3. Create directory `src/aeat/domain/financial/invoices/` with an empty
   `__init__.py` plus empty private modules:
   `_enums.py`, `_errors.py`, `_validators.py`, `_models.py`,
   `_service.py`, `_stubs.py`.
4. Run `uv run pytest tests/test_config.py -q` to confirm settings
   alignment gate.

## Phase 2 — Errors + enums + stubs

5. In `_errors.py` declare the exception hierarchy rooted at
   `InvoiceError(AeatError)`: `InvoiceCatalogueError`,
   `InvoicePersistenceError`, `InvoiceNotFoundError`,
   `InvoiceLinkError`, `InvoiceLinkInconsistencyError` (carries
   `invoice_path`, `transactions_path`, `invoice_id`,
   `transaction_id`).
6. In `_enums.py` declare `InvoiceKind`, `IvaRate`, `PaymentStatus`
   as the ADR specifies, plus the module-level
   `_IVA_RATE_PERCENTAGES: Mapping[IvaRate, Decimal | None]` (exposed
   via a module-private getter, not re-exported).
7. In `_stubs.py` declare `Protocol` placeholders for
   `SupportsAttachmentId` (forward-looking to #76) and
   `SupportsTaxCategoryId` (forward-looking to #77). Typing-only.

## Phase 3 — Validators

8. Implement `_validators.validate_country_code(value) -> str` —
   2-char ISO-3166 alpha-2 upper-cased.
9. Implement `_validators.validate_spanish_tax_id(value) -> str` —
   NIF, NIE, CIF algorithms per ADR. Return normalized upper-cased
   value. Raise `ValueError` on failure.
10. Implement `_validators.validate_vat_number(value, country) -> str`
    — requires country ISO-2 prefix followed by 4–20 alphanumerics.
11. Author `test_validators.py` with `@pytest.mark.unit` tests for
    each algorithm. Mandatory fixtures:
    - Valid NIF with every letter of the checksum alphabet covered
      across ≥3 cases.
    - Valid NIE for each of `X`, `Y`, `Z` leaders.
    - Valid CIF for each branch: digit-control (leading `A`, `B`,
      `E`, `H` digit-form), letter-control (leading `K`, `P`, `Q`,
      `R`, `S`, `N`, `W`), and the dual-accept `ABEH` letter-form
      case.
    - Invalid-checksum NIF/NIE/CIF fixtures for each shape.
    - VAT prefix enforcement: valid `DE…`, `FR…`, `ES…`; invalid
      missing-prefix; mismatching-country rejection.
    - Country code normalisation and invalid-length rejection.

## Phase 4 — Models (line, invoice, catalogue)

12. Implement `_models.InvoiceLine`:
    - Strict frozen `ConfigDict(strict=True, frozen=True,
      extra="forbid")`.
    - Field validators for `quantity` (>0), `unit_price` (>=0),
      `subtotal` (>=0), `iva_amount` (>=0), `description` (non-blank),
      `category_id` (trim; blank rejected, `None` allowed).
    - `model_validator(mode="after")` enforcing
      `abs(subtotal - quantity * unit_price) <= Decimal("0.01")`,
      and the IVA-rate / iva_amount coupling per ADR.
13. Implement `_models.Invoice`:
    - Strict frozen model with all fields from the ADR.
    - `model_validator(mode="before")` that canonicalises
      `kind`, `issued_at`, `counterparty_country`,
      `counterparty_tax_id`, `currency`, `grand_total`, computes
      `derive_invoice_id(...)`, and asserts parity with any caller-
      supplied `invoice_id`.
    - Field validators: strip / validate strings, normalise enums,
      normalise currency, freeze `lines` to a tuple, dedupe-preserve-
      order for `linked_transaction_ids`, enforce 64-char hex shape
      for each linked ID.
    - `model_validator(mode="after")` enforcing **exact** invoice-
      level arithmetic:
      `base_total == sum(line.subtotal)`,
      `iva_total == sum(line.iva_amount)`,
      `grand_total == base_total + iva_total`, and the all-exempt
      corollary.
14. Implement `derive_invoice_id(kind, invoice_number, issued_at,
    counterparty_tax_id, currency, grand_total)` — lowercase SHA-256
    hex digest over canonical JSON, consistent with
    `derive_transaction_id` style.
15. Implement `_models.InvoiceCatalogue`:
    - Strict frozen model with `invoices: Mapping[str, Invoice]`.
    - `from_invoices` constructor rejecting duplicate
      `invoice_id`.
    - Catalogue-level `__iter__ / __len__ / __contains__ / get /
      values`.
    - Mirror the `_freeze_transactions` / `_serialize_transactions`
      pattern for round-trip JSON support.
16. Public `__init__.py` re-exports the complete public surface:
    `InvoiceKind`, `IvaRate`, `PaymentStatus`, `Invoice`,
    `InvoiceLine`, `InvoiceCatalogue`, `InvoiceError`,
    `InvoiceCatalogueError`, `InvoicePersistenceError`,
    `InvoiceNotFoundError`, `InvoiceLinkError`,
    `InvoiceLinkInconsistencyError`, `ReconciliationSuggestion`,
    `LinkInconsistency`, `derive_invoice_id`, `find_invoice`,
    `find_unmatched`, `link_transaction`,
    `link_transaction_bidirectional`, `load_invoices`,
    `save_invoices`, `suggest_reconciliations`,
    `verify_link_consistency`.

## Phase 5 — Service layer

17. In `_service.py` implement `load_invoices(path) ->
    InvoiceCatalogue` and `save_invoices(catalogue, path) -> None` —
    atomic temp-file + `os.replace` pattern copied verbatim from the
    `#74` transaction service with the logger name updated.
18. Implement `find_invoice(catalogue, invoice_id) -> Invoice | None`
    and `find_unmatched(catalogue, *, kind=None) -> tuple[Invoice,
    ...]`.
19. Implement `link_transaction(catalogue, invoice_id, transaction_id)
    -> InvoiceCatalogue`:
    - 64-char lowercase hex validation for `transaction_id`.
    - Idempotency per ADR: duplicate link is a no-op returning a
      value-equal catalogue.
20. Implement `ReconciliationSuggestion` (strict frozen pydantic).
    Implement `suggest_reconciliations(invoices, transactions, *,
    amount_tolerance=Decimal("0.01"))` per ADR: deterministic, sorted
    by `(score desc, invoice_id asc, transaction_id asc)`.
21. Implement `LinkInconsistency` (strict frozen pydantic) and
    `verify_link_consistency(invoices, transactions) ->
    tuple[LinkInconsistency, ...]`.
22. Implement `link_transaction_bidirectional(invoices_path,
    transactions_path, invoice_id, transaction_id)`:
    - Load both, compute both new catalogues in memory, revalidate.
    - Write invoice side first, then transaction side.
    - If transaction save raises, attempt to restore the original
      invoice file; if restore fails, raise
      `InvoiceLinkInconsistencyError` with both paths.

## Phase 6 — CLI integration

23. Create `src/aeat/entrypoints/cli/financial/invoices.py` hosting a Typer
    app named `invoices` with commands `list`, `show`, `link`,
    `reconcile`, `verify`. Commands follow the pattern used by
    `src/aeat/entrypoints/cli/financial/txs.py`.
24. Register the app under `aeat financial invoices` in
    `src/aeat/entrypoints/cli/financial/__init__.py`.
25. Register a top-level alias `aeat invoices` in `src/aeat/entrypoints/cli/
    __init__.py` by adding the same Typer app as a sub-app.
26. Author CLI smoke tests in
    `src/aeat/domain/financial/invoices/test_cli.py` using Typer's
    `CliRunner`, exercising both the nested and aliased paths.

## Phase 7 — Tests

Every new test module MUST carry `@pytest.mark.unit` on each test
function and must avoid mocks / patches / stubs / fakes — only real
local fixtures built from in-repo types.

27. `test_validators.py` — covered in Phase 3 step 11.
28. `test_models.py`:
    - Construct a fully-valid ISSUED invoice; assert
      `invoice_id` is a 64-char lowercase hex string and stable
      across re-construction.
    - Mutation is rejected (frozen).
    - Line-level rounding within 1 cent is accepted; beyond is
      rejected.
    - Invoice-level totals require exact equality; per-line
      rounding at the 1-cent edge that accumulates to >1 cent at the
      invoice level is rejected.
    - EXEMPT / NOT_SUBJECT lines require `iva_amount == 0` exactly.
    - NIF / NIE / CIF validation is triggered when
      `counterparty_country == "ES"`.
    - VAT prefix validation is triggered otherwise.
    - `linked_transaction_ids` deduplication + shape validation.
    - `derive_invoice_id` is stable under equivalent Decimal
      representations.
29. `test_catalogue.py`:
    - Duplicate `invoice_id` is rejected on iterable construction.
    - JSON round-trip preserves the catalogue byte-for-byte
      (serialised output stable; load / save idempotent).
    - `link_transaction` returns a new catalogue, preserves the old,
      rejects non-hex transaction IDs, is idempotent on duplicates.
    - `find_unmatched` filters by kind correctly.
30. `test_reconciliation.py`:
    - ISSUED invoice + positive transaction matching by amount +
      counterparty substring emits a score-1 suggestion.
    - RECEIVED invoice + negative transaction matching emits a
      score-1 suggestion.
    - Amount-match-only (counterparty missing) emits score 0.5.
    - Counterparty-only (wrong amount) emits no suggestion.
    - Already-linked invoices are excluded.
    - Already-linked transactions are excluded.
    - Output is sorted deterministically.
    - `verify_link_consistency` detects one-sided links in both
      directions.
    - `link_transaction_bidirectional` success path updates both
      files; simulate transaction-write failure by providing an
      unwritable transactions path and assert the invoice file is
      restored to its prior contents.
    - Double-failure path: simulate both the transaction-write and
      the invoice-restore failing, and assert the raised error is an
      `InvoiceLinkInconsistencyError` carrying both paths and both
      IDs.
31. `test_cli.py`:
    - `aeat financial invoices list` returns the populated invoice
      table.
    - `aeat financial invoices list --kind issued` filters.
    - `aeat financial invoices show <id>` prints pydantic JSON.
    - `aeat financial invoices link <id> <tx-id>` updates both
      catalogue files and prints the updated invoice JSON.
    - `aeat financial invoices reconcile` prints tabular suggestions.
    - `aeat financial invoices reconcile --apply` performs the
      bidirectional link for each amount-matching suggestion.
    - `aeat financial invoices verify` exits `0` when consistent,
      `2` when an inconsistency is present.
    - `aeat invoices list` (top-level alias) behaves identically.
    - All tests use only real local fixtures — no mocks, patches,
      stubs, or fakes.

## Phase 8 — Gates

32. `uv run ruff check .`
33. `uv run ruff format --check .`
34. `uv run ty check` (project's type checker — substitute `mypy`
    if `ty` is unavailable).
35. `uv run pytest -q` (unit marker default; live gates remain off).
36. `uv run pre-commit run --files <changed files>` if the hook is
    installed.

## Phase 9 — Code review + ship

37. Load `vaultspec-code-reviewer` persona; run a full code review
    focused on: provenance chain preservation, pydantic strictness,
    IVA arithmetic correctness, bidirectional link atomicity,
    immutable-return discipline, CLI non-regression.
38. Action review findings in additional commits.
39. Commit via conventional-commits style:
    `feat(financial): add invoice catalogue with bidirectional
    transaction linking (#75)`.
40. Push `feature/75-invoice-catalogue` and open a PR annotated with
    the research, ADR, and plan artifact links.

## Issue-wording delta: "IBAN format checks"

Issue `#75`'s scope bullet mentions "IBAN / NIF format checks" in the
test list. IBAN lives on `RawTransaction` (T1, `#73`) and is already
validated upstream; it is not a field on `Invoice` or `InvoiceLine`.
This plan therefore implements NIF / CIF / VAT format checks (the
in-scope invoice identity fields) and explicitly leaves IBAN to the
T1 provider layer. The PR description should call this delta out so
reviewers do not expect an invoice-side IBAN validator.

## Out of scope (per ADR)

- Multi-currency FX conversion (`#103`).
- Attachment byte-level provenance (`#76`).
- Tax-category foreign key runtime types (`#77`).
- LLM-driven matching engine (`#89`).
- Split-payment reconciliation (one invoice, many transactions
  whose sum equals the grand total but no single one does).
- Schema-version migration (deferred to `#81`).

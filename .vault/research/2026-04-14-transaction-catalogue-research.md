---
tags:
  - "#research"
  - "#transaction-catalogue"
date: "2026-04-14"
modified: '2026-04-14'
related:
  - "[[2026-04-13-p2a-financial-provider-research]]"
  - "[[2026-04-13-p2a-financial-provider-adr]]"
  - "[[2026-04-13-p2a-financial-provider-plan]]"
  - "[[2026-04-13-cohesive-project-roadmap-reference]]"
---

# `transaction-catalogue` research: `tdp-t1-t2-seam`

This research grounds issue `#74` at the seam between T1 ingest and T2/T3 downstream consumers. The goal is to define a strict immutable transaction wrapper around `RawTransaction`, preserve provenance without mutation, keep sibling-branch imports out of the surface, and land a usable catalogue plus CLI on top of the existing `aeat.domain.financial` package.

## Findings

### Upstream contract already on main

- Issue `#73` already landed the T1 boundary on `main`: `aeat.domain.financial.RawTransaction` is the upstream producer contract and is publicly re-exported from both `aeat.domain.financial` and `aeat.domain.financial.providers`.
- The current `RawTransaction` shape differs from the older issue-body wording. It already carries `transaction_id`, `booked_date`, `value_date`, `amount`, `currency`, `counterparty`, `description`, `provenance`, and immutable `raw_fields`.
- `RawTransaction` is already strict, frozen, and provenance-rich. Issue `#74` therefore must wrap the raw record instead of redefining or normalizing T1.

### Provenance-chain invariant

- Issue `#104` defines the non-negotiable pipeline rule: every downstream record must preserve the full provenance chain back to its T1 raw source.
- Because `RawTransaction` is already frozen and stores immutable `raw_fields`, the safest implementation is to embed the raw object verbatim inside `Transaction` and never derive mutable copies of its payload.
- Any classification or linking operation must therefore return a new `Transaction` or `TransactionCatalogue` rather than mutating the wrapped raw record in place.

### Sibling-branch boundary constraints

- `src/aeat/adapters/outbound/aeat/export/` is explicitly out of scope and owned by `feature/117-live-submit-hardening`; only additive changes in `src/aeat/config.py` are allowed there.
- `src/aeat/domain/modelos/` is owned by `feature/108-modelo-inventory-catalogue`; transaction work must not touch the modelo catalogue and should import from `aeat.domain.modelos` only when needed. This issue does not need it.
- `src/aeat/domain/financial/invoices/` and `src/aeat/domain/financial/tax_categories/` are not on `main`, so invoice/category foreign keys must stay as plain `str | None` at runtime with internal `Protocol` placeholders used only for typing and documentation.
- The existing `src/aeat/domain/financial/categories/` package on `main` is not the future `tax_categories/` sibling described by the issue. The transaction package must avoid coupling to it to prevent locking in the wrong downstream dependency.

### Public API and package-shape precedent

- Existing financial subpackages on `main` follow the pattern `public __init__.py + private underscore modules + colocated tests`.
- The root `aeat.domain.financial` package re-exports only selected upstream boundaries. Child packages such as `aeat.domain.financial.vat` expose their own public surfaces and explicitly forbid deep imports.
- The transaction package should follow the same shape: `aeat.domain.financial.transactions` as the only public import surface, with implementation in underscored modules and no re-export of internal helpers.

### Transaction identity requirements

- The issue requires `transaction_id` to be a stable hash over `(provider_id, value_date, amount, narrative)`.
- The current `RawTransaction` uses `transaction_id` for the provider-emitted T1 identity, not a field named `provider_id`. The only viable source for the required hash input on `main` is therefore `raw.transaction_id`.
- The narrative source on `main` is `raw.description`; there is no `narrative` field yet. The transaction package must map the issue wording onto the current upstream contract and document that choice.
- Because catalogue keys are a single string and the code review mandate calls for collision safety, a fixed cryptographic digest with a versioned prefix is preferable to ad hoc concatenation. A lowercase SHA-256 hex digest over a canonical string payload is deterministic, portable, and sufficiently collision-resistant for catalogue keys.

### Classification semantics

- The issue’s four closed sets map cleanly to `enum.StrEnum`: transaction direction and business classification should be represented as uppercase symbolic values in Python with stable lowercase/explicit string payloads chosen to match existing project style.
- `business_pct` is meaningful only when classification is `MIXED`; otherwise it should be `None`. For `MIXED`, the accepted range must be inclusive `0..1` using `Decimal`, not float.
- `classified_by` is a constrained string rather than an enum because the issue allows the open-ended `rule:<rule-id>` shape. Validation therefore needs an allowlist for `"auto"` / `"manual"` plus a prefix rule for `"rule:"` with a non-empty suffix.
- `classified_at` should require timezone awareness if present, matching the provenance timestamp discipline already used in `RawProvenance`.

### Catalogue and persistence

- The issue explicitly wants one JSON file per catalogue, written with `model_dump_json(indent=2)` and read with `model_validate_json`.
- Current repo precedent for atomic persistence uses `os.replace` after writing a sibling temporary file. The transaction package can reuse that pattern directly.
- A `dict[str, Transaction]` model field alone does not let construction detect duplicate logical IDs when input arrives as an iterable of transactions, because duplicate keys would be collapsed before validation. The cleanest solution is to accept mapping input for persistence round-trip and provide a constructor helper that builds from an iterable while rejecting repeated `transaction_id` values explicitly.
- The catalogue should still implement `__iter__`, `__len__`, and `__contains__` so callers can treat it like a lightweight immutable container without reaching into its backing dictionary.

### CLI integration and settings

- `aeat financial` already exists as a Typer sub-app with `ingest` registered directly on the subgroup. The transaction commands should extend that existing subgroup with a nested `txs` Typer app instead of creating a parallel root command.
- `tests/test_config.py` enforces a strict 1:1 mapping between `Settings` fields and `env/.env.example`; the new transaction directory setting must update both files in the same change.
- The canonical live-test flag in the repo is already `AEAT_LIVE_TESTS_ENABLED`, and this issue is fully unit-testable, so no new live gates are needed.

### Verification strategy

- Colocated unit tests under `src/aeat/domain/financial/transactions/` match the repo’s current style for financial subpackages.
- CLI smoke tests should exercise the root `aeat` app via `CliRunner`, as existing `aeat financial` tests do.
- The strongest regression checks for this issue are deterministic hash stability, immutable-return semantics for catalogue updates, JSON round-trip, and explicit validation of `business_pct` / `classified_by`.

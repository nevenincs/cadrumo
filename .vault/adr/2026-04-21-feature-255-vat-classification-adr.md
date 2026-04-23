---
tags:
  - '#adr'
  - '#feature-255-vat-classification'
date: '2026-04-21'
related:
  - '[[2026-04-21-feature-255-vat-classification-research.md]]'
---

# `feature-255-vat-classification` adr: `VAT Classification CLI Integration` | (**status:** `accepted`)

## Problem Statement

Kent needs the ability to trigger the VAT classification engine from the CLI. This involves creating a new `aeat vat classify` command and modifying the `aeat financial invoices show` command to surface the classification result. Additionally, the classification category and rule need to be stored in the `Invoice` schema.

## Considerations

- The `classify_vat` function requires `VATClassificationCriteria`, which takes multiple axes (e.g., residency, supply type, etc.).
- When classifying from an invoice (`--from-invoice`), we must derive these criteria from the `Invoice` model's fields.
- The `Invoice` model needs to persist the classification result to avoid recomputing it and to allow overrides.

## Constraints

- The `Invoice` model is strictly frozen (`_STRICT_FROZEN`). Any new fields must be optional or have defaults so existing serialized invoices don't break on load.
- CLI commands must exit cleanly and provide human-readable errors.
- Ad-hoc classification needs sufficient CLI arguments to build the `VATClassificationCriteria`.

## Implementation

1.  **Schema Extension**: Extend `Invoice` in `src/aeat/financial/invoices/_models.py` with `vat_category: VATCategory | None = None` and `vat_rule_fired: str | None = None`.
2.  **Helper Function**: Create a mapper `infer_classification_criteria(invoice)` to bridge the `Invoice` fields to `VATClassificationCriteria`.
3.  **CLI Command - `aeat vat classify`**: Add a new command to `src/aeat/cli/vat.py`.
    - Implement `--from-invoice` which loads the invoice from the catalogue, infers criteria, runs `classify_vat`, and prints the result.
    - Implement ad-hoc classification flags (`--counterparty-country`, `--supply-type`, `--counterparty-has-vat-id`) to run the engine manually.
4.  **CLI Command - `aeat financial invoices show`**: The `show_cmd` naturally outputs the whole JSON representation of the `Invoice`, so extending the schema fulfills this requirement.

## Rationale

Storing `vat_category` and `vat_rule_fired` on the `Invoice` model ensures that the state is cached and user-overridable. Providing a helper to map `Invoice` to `VATClassificationCriteria` centralizes the logic for both `--from-invoice` and the future `add` command.

## Consequences

Existing invoices in the JSON store will load with `vat_category=None`. The system must handle this gracefully. The ad-hoc CLI will require parsing strings into enums like `TransactionKind`.

---
tags:
  - '#plan'
  - '#feature-255-vat-classification'
date: '2026-04-21'
related:
  - '[[2026-04-21-feature-255-vat-classification-adr.md]]'
---

# `feature-255-vat-classification` `phase-1` plan

Integrate the VAT classification engine into the `aeat` CLI so Kent can manually classify transactions.

## Proposed Changes

We will extend the `Invoice` schema to store classification results and introduce the `aeat vat classify` command. This builds on the decisions outlined in `[[2026-04-21-feature-255-vat-classification-adr.md]]`.

## Tasks

- `Phase 1`
  1. `Step 1.1: Extend Invoice Schema`: Update `src/aeat/financial/invoices/_models.py` `Invoice` model with `vat_category: VATCategory | None = None` and `vat_rule_fired: str | None = None`. Add to JSON serialization/deserialization.
  2. `Step 1.2: Implement Mapper`: In `src/aeat/financial/vat/_classification.py` or a new module, add `infer_classification_criteria(invoice)`. It should map country, tax id, etc. to `VATClassificationCriteria`.
  3. `Step 1.3: Implement CLI Command`: In `src/aeat/cli/vat.py`, add `@app.command(name="classify")`. Support `--from-invoice` and ad-hoc flags `--counterparty-country`, `--supply-type`, `--counterparty-has-vat-id`. Also provide a human-readable error when criteria are insufficient.
  4. `Step 1.4: Update Tests`: Add `pytest.mark.unit` tests to `src/aeat/cli/test_vat_cli.py` and `src/aeat/financial/invoices/test_models.py` verifying the new CLI behavior and model extensions.

## Verification

We will run unit tests via `just test` and verify that running `aeat vat classify` works as expected. We will specifically check the test cases defined in the GH issue (GB services, etc.).

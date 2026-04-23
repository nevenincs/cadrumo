---
tags:
  - "#research"
  - "#feature-255-vat-classification"
date: 2026-04-21
related:
  - "[[2026-04-18-kent-data-prep-journey-audit.md]]"
---

# Feature 255: VAT Classification CLI - Research

## Context
Kent needs the ability to ask the tool to classify VAT treatment via the CLI. The engine `classify_vat` exists in `src/aeat/financial/vat/_classification.py` and implements a closed-table decision engine with 15 typed rules.

## Scope
1. **New CLI Command**: `aeat vat classify`
   - `--from-invoice INVOICE_ID`: Loads an invoice, constructs `VATClassificationCriteria`, and classifies. Returns category + rule ID + citation.
   - Ad-hoc mode: `--counterparty-country CODE --supply-type SUPPLY_TYPE --counterparty-has-vat-id` (and potentially other criteria as needed for manual classification).
2. **Auto-run on `invoices add`**: During `aeat financial invoices add`, the tool should run classification to default the VAT category on ingestion, allowing user override. (Wait, epic #254 introduces `invoices add`, need to check if it exists).
3. **Surface on `invoices show`**: Output of `aeat financial invoices show` needs new fields: `vat_category` and `vat_rule_fired`.
4. **Error Handling**: Provide human-readable errors when criteria are insufficient to classify.

## Current Codebase Analysis
- **VAT Classification Engine**: Located at `src/aeat/financial/vat/_classification.py`. Exposes `classify_vat` which takes a `VATClassificationCriteria` pydantic model.
- **Criteria fields**:
  - `transaction_date`
  - `issuer_residency` (ES_MAINLAND, EU_MEMBER, THIRD_COUNTRY, etc)
  - `customer_residency`
  - `customer_tax_status` (B2B_VAT_REGISTERED, B2C_CONSUMER, etc)
  - `kind` (TransactionKind.GOODS, SERVICES_GENERAL, etc)
  - `direction` (InvoiceDirection.ISSUED, RECEIVED)
  - `issuer_member_state`
  - `customer_member_state`
  - `rate_tier`
- **CLI Sub-apps**:
  - `aeat vat` is defined in `src/aeat/cli/vat.py`.
  - `aeat financial invoices` is defined in `src/aeat/cli/financial/invoices.py`.
- **Invoices Model**: Defined in `src/aeat/financial/invoices/_models.py`. Needs fields `vat_category` and `vat_rule_fired` added if not present.

## Implementation Considerations
- **`aeat vat classify` CLI**: Needs to construct `VATClassificationCriteria`.
  - For `--from-invoice`: we map invoice fields to criteria. `Invoice` model has `counterparty_country`, `counterparty_tax_id`, `kind`, `issued_at`, etc. We assume the issuer is the autonomous professional (for issued invoices) or the counterparty (for received).
  - The `Invoice` model might need an update to store `vat_category` and `vat_rule_fired`. Let's check `src/aeat/financial/invoices/_models.py`.

## Next Steps
1. Write the ADR for the implementation plan.
2. Review `src/aeat/financial/invoices/_models.py` and `_service.py` to understand the invoice structure.
3. Plan the CLI interface for `aeat vat classify` and modifications to `aeat financial invoices`.

---
tags:
  - "#adr"
  - "#category-assignment"
date: 2026-04-18
related:
  - "[[2026-04-18-category-assignment-cli-research]]"
---

# category-assignment-cli-adr

## status

Accepted

## context

GitHub Issue #253 requires Kent to be able to assign a spending category to a transaction using the CLI. This is a blocker for the Classification milestone.
The current `aeat financial txs classify` command only allows setting the high-level business classification (e.g., BUSINESS, PERSONAL, MIXED) and a business percentage. It lacks the ability to assign a specific spending category from the 39-category catalogue or provide a reason for the classification.

However, our research (`[[2026-04-18-category-assignment-cli-research]]`) confirms that the underlying `Transaction` domain model already supports `category_id` and `notes` fields. The `set_classification` service function simply needs to be updated to accept and persist these fields, and the CLI command needs new arguments to capture them from the user.

## decision

We will extend the `aeat financial txs classify` command to support two new optional flags:
- `--category`: Validated against the `SpendingCategory` enum (which represents the 39-category catalogue).
- `--reason`: A string to capture the user's reasoning for the classification, mapped to the `notes` field.

The `set_classification` service function in `src/aeat/domain/financial/transactions/_service.py` will be modified to accept these two optional arguments and apply them when creating the updated `Transaction` instance.

## consequences

**Positive:**
- Unblocks the Classification milestone (DP6).
- Reuses existing domain model fields (`category_id` and `notes`), avoiding database or schema migrations.
- Provides a seamless CLI experience for Kent to fully classify a transaction in one command.

**Negative:**
- The CLI command signature grows, but since the new flags are optional, it remains backward compatible for simpler classifications.

**Neutral:**
- Will require updating the unit tests in `src/aeat/domain/financial/transactions/test_cli.py` to ensure the new flags are properly parsed and persisted.

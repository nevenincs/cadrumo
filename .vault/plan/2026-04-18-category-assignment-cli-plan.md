---
tags:
  - "#plan"
  - "#category-assignment"
date: 2026-04-18
modified: '2026-04-18'
related:
  - "[[2026-04-18-category-assignment-cli-adr]]"
  - "[[2026-04-18-category-assignment-cli-research]]"
---
# category-assignment-cli-plan

## Objective
Implement category assignment for transactions via the CLI to resolve GitHub Issue #253.

## Scope
Extend `aeat financial txs classify` to support `--category` and `--reason` flags. Update the backend service `set_classification` to persist these values.

## Steps

### 1. Update `set_classification` service
- **File:** `src/aeat/domain/financial/transactions/_service.py`
- **Action:** Update the `set_classification` signature to accept `category_id: str | None = None` and `notes: str | None = None` (as keyword-only arguments).
- **Action:** Include these new parameters in the `_validate_transaction_update` payload mapping.

### 2. Update CLI command `classify_cmd`
- **File:** `src/aeat/entrypoints/cli/financial/txs.py`
- **Action:** Add `category` option typed as `SpendingCategory | None = typer.Option(None, "--category", ...)` mapping to the `SpendingCategory` enum from `src/aeat/domain/financial/categories/_spending_category.py`.
- **Action:** Add `reason` option typed as `str | None = typer.Option(None, "--reason", ...)`.
- **Action:** Pass `category_id=category.value if category else None` and `notes=reason` to `set_classification`.

### 3. Update tests
- **File:** `src/aeat/domain/financial/transactions/test_cli.py`
- **Action:** Add a test verifying that `aeat financial txs classify --as BUSINESS --category cuotas_autonomos_ss --reason "Quota"` correctly assigns the `category_id` and `notes` and persists them.

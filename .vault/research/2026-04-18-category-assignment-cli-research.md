---
tags:
  - "#research"
  - "#category-assignment"
date: 2026-04-18
modified: '2026-04-18'
related:
---

# category-assignment cli research

## Objective
Research the `src/aeat/entrypoints/cli/financial/txs.py` CLI module and the `Transaction` domain model to support adding `--category` and `--reason` flags to the `aeat financial txs classify` command.

## Findings

### 1. `Transaction` Domain Model (`src/aeat/domain/financial/transactions/_models.py`)
The `Transaction` model already supports the necessary fields to persist category assignment and reasoning:
- `category_id: str | None = None`: Used to store the assigned category.
- `notes: str = ""`: Can be used to store the reasoning (`--reason`).

### 2. `set_classification` Service (`src/aeat/domain/financial/transactions/_service.py`)
The `set_classification` function currently accepts `classification`, `business_pct`, and `classified_by`.
To support category assignment, it needs to be updated to optionally accept `category_id` and `notes`. It should pass these directly when rebuilding the `Transaction` object.

### 3. `SpendingCategory` Catalogue (`src/aeat/domain/financial/categories/_spending_category.py`)
The 39-category catalogue corresponds to the `SpendingCategory` enum (e.g., `CUOTAS_COLEGIALES`, `CUOTAS_AUTONOMOS_SS`, etc.). The `--category` flag will validate against this enumeration. It contains exactly 39 categories.

### 4. CLI Command `classify_cmd` (`src/aeat/entrypoints/cli/financial/txs.py`)
The current command signature:
```python
def classify_cmd(
    transaction_id: str = typer.Argument(..., help="Stable transaction identifier."),
    classification: BusinessClassification = typer.Option(
        ...,
        "--as",
        case_sensitive=False,
        help="Classification target: BUSINESS, PERSONAL, MIXED, or UNCLASSIFIED.",
    ),
    pct: str | None = typer.Option(
        None,
        "--pct",
        help="Business-use percentage in the inclusive 0..1 range for MIXED.",
    ),
)
```
Needs to be extended to:
- Add `category: SpendingCategory | None = typer.Option(None, "--category", case_sensitive=False, help="...")`
- Add `reason: str | None = typer.Option(None, "--reason", help="...")`

When provided, these values must be passed to the updated `set_classification` service function.

## Conclusion
The foundational models already support the required fields (`category_id` and `notes`). The scope of work is limited to:
1. Extending `set_classification` to accept `category_id` and `notes`.
2. Extending `classify_cmd` in `src/aeat/entrypoints/cli/financial/txs.py` to accept `--category` (typed as `SpendingCategory`) and `--reason` (typed as `str`).
3. Updating tests in `test_cli.py` to ensure correct assignment and validation.

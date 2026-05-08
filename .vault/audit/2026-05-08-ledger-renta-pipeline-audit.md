---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/audit/ location)
# Feature tag (replace ledger-renta-pipeline with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#audit'
  - '#ledger-renta-pipeline'
# ISO date format (e.g., 2026-02-06)
date: '2026-05-08'
# Related documents as quoted wiki-links
# (e.g., "[[2026-02-04-feature-research]]")
related:
  - "[[2026-05-08-ledger-renta-pipeline-plan]]"
  - "[[2026-05-08-ledger-renta-pipeline-phase2-contract-decisions-adr]]"
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `ledger-renta-pipeline` audit: `phase3-code-review`

## Scope

Phase 3 production and test changes for the strict Renta
ledger-expense observation and deductibility evaluator surface.

Reviewed files:

- `src/aeat/domain/renta/_ledger_expenses.py`
- `src/aeat/domain/renta/__init__.py`
- `src/aeat/domain/renta/test_ledger_expenses.py`

## Findings

No open findings after review.

Review hardening applied before this audit was finalized:

- `RentaDeductibilityResult` now validates that `category_family`
  matches `category`.
- `RentaDeductibleExpenseObservation` now validates that
  `category_family` matches `category`.
- `RentaDeductibleExpenseObservation` now validates that
  `target_casilla` matches the first-slice category mapping.

## Recommendations

Proceed to Phase 4 repository-backed aggregation. Keep the Phase 3
models pure and side-effect-free; repository loading should remain
outside the Renta domain models.

Verification completed:

- `uv run pytest src/aeat/domain/renta/test_ledger_expenses.py src/aeat/domain/renta/test_substrate.py`
- `uv run ruff check src/aeat/domain/renta/_ledger_expenses.py src/aeat/domain/renta/test_ledger_expenses.py src/aeat/domain/renta/__init__.py`
- `uv run ty check src/aeat/domain/renta`

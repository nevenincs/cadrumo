---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'W04.F02'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-20-live-iva-compensation-wallet-review-audit]]'
---

# W04.F02 ledger status IVA tax diagnostics

## Scope

- Follow-up: `W04.F02`
- Goal: make ledger status output show the tax fields needed to understand IVA calculation readiness blockers.

## Changes

- Confirmed `ledger view` already renders category, taxable base, IVA rate, IVA amount, and business classification.
- Extended `ledger status --period` with one `readiness_issue` row per ledger preflight issue.
- Each issue row includes transaction id, business classification, category id, taxable base, IVA rate, IVA amount, issue reason, and issue detail.
- Added a CLI regression that creates a real bucket-local business transaction missing IVA facts and verifies status output exposes the diagnostic fields.

## Verification

- `uv run pytest src/aeat/entrypoints/cli/test_ledger_preflight_verb.py::test_status_period_readiness_issues_include_tax_diagnostic_fields src/aeat/entrypoints/cli/test_ledger_preflight_verb.py::test_preflight_empty_catalogue_is_ready -q` completed with 2 passed.
- `uv run ruff check src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_ledger_preflight_verb.py` passed.

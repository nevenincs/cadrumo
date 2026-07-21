---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-08'
step_id: 'S05'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

# Harden classify-transactions.md

## Scope

- `docs/how-to/classify-transactions.md`

## Description

- Verify-close: read `classify-transactions.md` in full against the hardening standard and confirm its audit findings are resolved at HEAD.
- Confirm finding M6 (mixed-use classification unreachable from the documented verb): the page now documents the real working flow - `ledger ratios eligible` -> `ratios set <category-id> N` -> `ledger allocate <tx> --business-pct N --usage-ratio-id <category-id>` - and drops the false "most users need only `--business-pct`" claim.
- Confirm finding m15 (deductible-expense rows need `--category-id`): the page documents the category-id requirement and the `ledger categories` lookup.
- Confirm every documented command resolves against the live CLI.

## Outcome

- Page verified compliant at HEAD; audit findings M6 and m15 resolved (2026-06-19 batch). Delta: none required this pass.
- Imperative instruction steps, precondition block, safety note ("nothing is sent to AEAT"), Spanish-runtime note, resolving cross-links.

## Notes

- Residual m6 (ledger list prints no column headers) is an APP-side ergonomics finding, out of documentation-hardening scope. CLI conformance gate green.

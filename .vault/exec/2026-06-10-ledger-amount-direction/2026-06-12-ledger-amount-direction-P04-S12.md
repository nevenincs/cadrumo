---
tags: ['#exec', '#ledger-amount-direction']
date: '2026-06-12'
modified: '2026-07-17'
body_hash: 'sha256:9c353aff730751f11832bc57172ab7cbff51aac554afaba612ff3e11082125a1'
step_id: 'S12'
related:
  - '[[2026-06-10-ledger-amount-direction-plan]]'
---

# CLI Amount Magnitude Gate

## Scope

Step `P04.S12`.

## Description

- Added `_parse_amount_magnitude` for `ledger add --amount`.
- Reused the same magnitude parser for `ledger update --amount`.
- Added localized negative-amount messages naming the non-negative amount plus `--direction` shape.

## Outcome

CLI amount mutation surfaces reject negative ledger magnitudes before backend command construction.

## Notes

Locale updates were applied through `aeat.locales set` and verified with `scaffold --check`.

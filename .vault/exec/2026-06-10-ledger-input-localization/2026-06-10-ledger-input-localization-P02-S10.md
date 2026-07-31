---
tags:
  - '#exec'
  - '#ledger-input-localization'
date: '2026-06-12'
modified: '2026-07-17'
body_hash: 'sha256:412257527c848aa3643944d73b17a00a54f56c56521347556bdf536268f75ce6'
step_id: 'S10'
related:
  - "[[2026-06-10-ledger-input-localization-plan]]"
---

# Append expected-format hint to cli.ledger.errors.invalid_decimal in all four locales (en, es, ca, hu) via python -m aeat.locales set

## Scope

- `hint must name the accepted form: dot decimal separator`
- `no thousands grouping`
- `e.g. 1234.56`
- `src/aeat/locales/`

## Description

- Appended the expected-format hint (dot decimal separator, no thousands grouping, e.g. 1234.56) to `cli.ledger.errors.invalid_decimal` in all four locales via the `aeat.locales` CLI.

## Outcome

Done. Verified at HEAD: all four locales carry the accepted-form hint in `invalid_decimal`, alongside the `%{label}`/`%{raw}` tokens.

## Notes

None.

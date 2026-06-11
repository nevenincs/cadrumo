---
tags: ['#exec', '#modelo-locales-cli']
date: '2026-06-11'
step_id: 'S21'
related:
  - '[[2026-06-11-modelo-locales-cli-plan]]'
---

# P04.S21 run locale and registry verification gates

Scope: `src/aeat/locales`.

## Description

- Run focused ruff on the touched locale and registry test surfaces.
- Run focused pytest for modelo manager tests, modelo CLI tests, registry locale loader tests, and registry locale parity tests.
- Run `python -m aeat.locales scaffold --check` and `python -m aeat.locales audit`.
- Fill two missing eager locale keys in `ca` and `hu` through `python -m aeat.locales set`.
- Record seeded modelo coverage for M100, M130, M200, and M303.
- Run `vault plan check` for the modelo-locales-cli plan.

## Outcome

The feature-owned code, generic locale catalogue, seeded modelo coverage, registry locale tests, and plan structure checks pass.

## Notes

Verification evidence:

- `ruff check` passed for the touched locale and registry test files.
- `pytest ... -q -m "unit or integration"` passed with 21 tests.
- `python -m aeat.locales scaffold --check` reported `ca.yml`, `en.yml`, `es.yml`, and `hu.yml` ok.
- `python -m aeat.locales audit` reported `ca.yml`, `en.yml`, `es.yml`, and `hu.yml` ok.
- Seeded coverage remained M100 `3/2068`, M130 `20/20`, M200 `2/3232`, and M303 `2/120` for each non-Spanish seeded locale.
- `vault plan check` passed for the plan.

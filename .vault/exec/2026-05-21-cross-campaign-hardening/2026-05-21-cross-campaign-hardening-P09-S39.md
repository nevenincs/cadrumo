---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P09.S39'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P09.S39`

Closed GEN-3 task 517.

- Verified: `src/aeat/application/modelo/test_declaration_period_binding.py`

## Description

Confirmed the remaining GEN-3 work was already covered by the P08.S35
implementation. The current declaration-period binding suite includes
non-303 period-token coverage for `_resolve_declaration_period_inputs`:
Modelo 111 monthly period `03` resolves to `Decimal("3")`, and Modelo
100 annual period `0A` resolves to `Decimal("0")`.

No code change was required for this row.

## Tests

`uv run ruff check src/aeat/application/modelo/test_declaration_period_binding.py` passed.

`uv run pytest src/aeat/application/modelo/test_declaration_period_binding.py -q` passed with 9 tests in 37.84s.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S39` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P09-S39.md src/aeat/application/modelo/test_declaration_period_binding.py` passed.

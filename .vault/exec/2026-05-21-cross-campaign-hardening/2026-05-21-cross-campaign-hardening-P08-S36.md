---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P08.S36'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P08.S36`

Closed BIND-8/BIND-9.

- Modified: `src/aeat/domain/calculations/registry/test_invoice_bindings.py`
- Verified: `src/aeat/domain/calculations/registry/test_detail_record_modelo_coverage.py`
- Verified: `.vault/plan/2026-05-21-cross-campaign-hardening-plan.md`

## Description

Replaced the stale `item.source != "invoice"` fixture selection in
`test_invoice_bindings.py` with the named Modelo 130 previous-filing
binding `modelo-130-resultados-negativos-anteriores`. This makes the
test independent of future invoice source-kind retirement work.

Verified BIND-9 is already dispositioned in committed registry tests:
Modelo 184 uses `atribucion_member` and Modelo 360 uses
`refund_operation`, both covered by the detail-record row-set tests.

No fakes, mocks, monkeypatches, skipped tests, or copied business logic
were introduced.

## Tests

`uv run ruff check src/aeat/domain/calculations/registry/test_invoice_bindings.py src/aeat/domain/calculations/registry/test_detail_record_modelo_coverage.py` passed.

`uv run pytest src/aeat/domain/calculations/registry/test_invoice_bindings.py src/aeat/domain/calculations/registry/test_detail_record_modelo_coverage.py -q` passed with 31 tests in 16.64s.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S36` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P08-S36.md src/aeat/domain/calculations/registry/test_invoice_bindings.py src/aeat/domain/calculations/registry/test_detail_record_modelo_coverage.py` passed.

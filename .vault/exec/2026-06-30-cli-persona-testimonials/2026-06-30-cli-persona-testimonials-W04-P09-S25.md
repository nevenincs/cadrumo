---
tags:
  - '#exec'
  - '#cli-persona-testimonials'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S25'
related:
  - '[[2026-06-30-cli-persona-testimonials-plan]]'
---

# W04.P09.S25 EU VAT Advisory And Foreign-Currency IVA Diagnostics

Scope: IVA category advisory wording, IVA aggregation, and ledger preflight readiness.

## Description

RAG grounding:

- `uvx vaultspec-rag search "EU VAT unsupported currency reverse charge diagnostics invoice classification" --type code`
- `uvx vaultspec-rag search "converted foreign currency IVA ledger aggregation taxable_base iva_amount amount_eur unsupported currency" --type code`
- `uvx vaultspec-rag search "converted foreign currency IVA preflight unsupported currency eur tax substrate taxable_base iva_amount" --type code`
- `uvx vaultspec-rag search "EU VAT export zero rated advisory wording saturation evidence verify" --type code`

EU VAT/reverse-charge/export saturation wording now stays advisory: it says
`potential` and asks the operator to verify evidence instead of treating category
selection as filing/legal certainty. Converted non-EUR IVA rows now fail closed in
both aggregation and preflight with `MISSING_EUR_TAX_SUBSTRATE` because the product
does not model EUR-projected taxable base and cuota separately from native tax
facts. Unconverted non-EUR rows remain `UNSUPPORTED_CURRENCY`.

## Outcome

Changed:

- `src/aeat/domain/iva/_saturation.py`
- `src/aeat/domain/iva/tests/test_saturation.py`
- `src/aeat/application/aggregation/_iva_ledger.py`
- `src/aeat/application/aggregation/tests/test_iva_ledger.py`
- `src/aeat/application/ledger/_preflight.py`
- `src/aeat/application/ledger/tests/test_preflight_anomaly.py`

Review found and resolved a preflight/aggregation mismatch. Final review found no
remaining issues in the scoped behavior. Residual risk: future support for
converted foreign IVA aggregation needs explicit EUR taxable-base/cuota modeling.

## Verification

Passed:

- `uv run --no-sync pytest src/aeat/domain/iva/tests/test_saturation.py` -> 27 passed.
- `uv run --no-sync pytest src/aeat/domain/iva/tests` -> 270 passed.
- `uv run --no-sync pytest src/aeat/application/aggregation/tests/test_iva_ledger.py::test_converted_foreign_currency_tax_substrate_does_not_project_as_eur -q` -> 1 passed.
- `uv run --no-sync pytest src/aeat/application/aggregation/tests/test_iva_ledger.py -q` -> 27 passed in the worker run.
- `uv run --no-sync pytest src/aeat/application/aggregation/tests -q` -> 483 passed in the worker run.
- `uv run --no-sync pytest src/aeat/application/ledger/tests/test_preflight_anomaly.py src/aeat/domain/iva/tests/test_saturation.py -q` -> 34 passed.
- Final reviewer focused checks: preflight anomaly test -> 5 passed; converted aggregation test -> 1 passed; export wording test -> 2 passed.
- Isolated latest-HEAD worktree focused P09 command -> 69 passed.
- W04 touched-file ruff gate in isolated latest-HEAD worktree passed.

Latest isolated full-file retest note: full `test_iva_ledger.py` remains blocked
by unrelated registry source-catalogue byte-count failures in registry-loading
tests. The S25-specific behavior is covered and passing.


---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W61.P303.S1816'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr]]"
---

# `cli-workflow-redesign` `W61.P303.S1816`

Closed plan rows:

- `W61.P303.S1816`

## Description

Implemented legal IVA prorrata reference carrying across VAT domain logic and IVA ledger aggregation without conflating prorrata references with usage ratios.

Legal prorrata references are canonical domain values shaped as `prorrata:{year}:{kind}:{regime}` with optional `:{sector_id}`. They identify statutory IVA prorrata context and remain separate from proportional business/private usage ratios.

`validate_prorrata_reference` trims input, parses canonical reference parts, validates year bounds from `2000` through `2100`, validates `ProrrataKind` and `ProrrataRegime`, and wraps Pydantic validation failures as `ProrrataInputError`.

`compute_prorrata_general` now wraps invalid result-window validation as `ProrrataInputError`, resolving the S1816 audit finding. The S1816 audit records the prior MEDIUM finding as resolved, with no HIGH or CRITICAL issues remaining.

IVA aggregation now carries `prorrata_references` separately from IVA ledger observations and aggregation issues. Aggregation validates `transaction.prorrata_reference` after taxable base, IVA amount, IVA rate, and business proportionality are resolved. Mixed rows apply business percentage before carrying prorrata base and input VAT amounts.

Prorrata references are carried only for supported input VAT rows (`SOPORTADO`). Output VAT rows retain their IVA ledger observation and emit `INVALID_PRORRATA_REFERENCE`. Invalid prorrata strings also retain the IVA ledger observation and emit an issue instead of dropping the row.

## Modified Paths

- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
- `.vault/audit/2026-05-14-cli-workflow-redesign-W61-P303-S1816-code-review-audit.md`
- `src/aeat/domain/vat/_prorrata.py`
- `src/aeat/domain/vat/__init__.py`
- `src/aeat/domain/vat/test_prorrata.py`
- `src/aeat/application/aggregation/_iva_ledger.py`
- `src/aeat/application/aggregation/__init__.py`
- `src/aeat/application/aggregation/test_iva_ledger.py`

## Tests

- `uv run --no-sync ruff check src/aeat/domain/vat/_prorrata.py src/aeat/domain/vat/__init__.py src/aeat/domain/vat/test_prorrata.py src/aeat/application/aggregation/_iva_ledger.py src/aeat/application/aggregation/__init__.py src/aeat/application/aggregation/test_iva_ledger.py`
  - All checks passed
- `uv run --no-sync ty check src/aeat/domain/vat/_prorrata.py src/aeat/domain/vat/__init__.py src/aeat/domain/vat/test_prorrata.py src/aeat/application/aggregation/_iva_ledger.py src/aeat/application/aggregation/__init__.py src/aeat/application/aggregation/test_iva_ledger.py`
  - All checks passed
- `uv run --no-sync pytest src/aeat/application/aggregation/test_iva_ledger.py src/aeat/domain/vat/test_prorrata.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py -q`
  - 76 passed

Coverage includes canonical prorrata reference parsing, invalid prorrata input error wrapping, invalid result-window error wrapping, separate IVA ledger observations, separate prorrata reference aggregation, supported input VAT prorrata carrying, output VAT invalid-reference issues, invalid-reference issue emission, and mixed-row business percentage application before prorrata base and input VAT carrying.

## Residuals

Legal IVA prorrata references, IVA ledger observations, aggregation issues, and usage ratios remain distinct concepts.

This step carries and validates prorrata references in VAT domain and IVA ledger aggregation surfaces.

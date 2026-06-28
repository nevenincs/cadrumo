---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr]]'
---



# `cli-workflow-redesign` Code Review

Focused review for `W61.P303.S1817` covering `src/aeat/application/ledger/_preflight.py`, `src/aeat/application/ledger/__init__.py`, `src/aeat/application/ledger/test_preflight.py`, `src/aeat/application/aggregation/_iva_ledger.py`, `src/aeat/application/aggregation/__init__.py`, and adjacent IVA ledger tests.

Summary: no HIGH or CRITICAL findings identified. The scoped implementation uses backend Pydantic models, AEAT base-error subclasses, repository-backed tests, and keeps usage-ratio proportionality separate from legal IVA prorrata. One MEDIUM behavior mismatch was found in preflight issue classification for internal transfer rows.

W61.P303.S1817-001 | MEDIUM | Internal transfer rows can be falsely blocked as missing business classification

`src/aeat/application/ledger/_preflight.py` checks `business_classification` before checking whether the ledger direction can feed modelo IVA aggregation. As a result, an in-period `INTERNAL_TRANSFER` row whose classification is still `NOT_YET_PROCESSED` produces `missing_business_classification` instead of being excluded as a non-tax settlement flow. This is visible in `src/aeat/application/ledger/test_preflight.py`, where the test name says internal transfers are ignored but the assertion expects a missing-classification issue from the transfer row.

This conflicts with the adjacent IVA aggregation behavior in `src/aeat/application/aggregation/_iva_ledger.py`, which checks direction first and reports internal transfers as `unsupported_direction` without requiring business classification or tax facts. It can make ledger preflight fail on transfer rows that are outside modelo calculation readiness, creating a false operator blocker.

Recommended follow-up: evaluate non-modelo directions before classification in preflight, or emit an explicit non-blocking unsupported-direction trace if preflight must account for them. Add a focused test proving an unclassified internal transfer does not produce a missing classification/category/base/IVA/proportionality blocker.

Verification: `uv run pytest src/aeat/application/ledger/test_preflight.py src/aeat/application/aggregation/test_iva_ledger.py` could not start because `.venv/Scripts/aeat.exe` was locked by another process. Retried with `.venv/Scripts/python.exe -m pytest src/aeat/application/ledger/test_preflight.py src/aeat/application/aggregation/test_iva_ledger.py`; result: 23 passed.

## Remediation Re-review

W61.P303.S1817-001-RR | INFO | Prior MEDIUM finding resolved

The remediation in `src/aeat/application/ledger/_preflight.py` now evaluates non-modelo ledger directions before business-classification readiness. In-period `INTERNAL_TRANSFER` rows therefore return no preflight readiness issue instead of being falsely reported as `missing_business_classification`.

`src/aeat/application/ledger/test_preflight.py` now asserts the in-period personal/internal-transfer-only set has `report.issues == ()` and `report.ready is True`, directly covering the prior false-blocker case. No HIGH or CRITICAL issues remain in the remediation scope.

Verification: `.venv/Scripts/python.exe -m pytest src/aeat/application/ledger/test_preflight.py`; result: 5 passed.

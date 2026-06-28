---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr]]'
---

# `W61.P303.S1816` Code Review

Review scope: `src/aeat/domain/vat/_prorrata.py`, `src/aeat/domain/vat/__init__.py`, `src/aeat/domain/vat/test_prorrata.py`, `src/aeat/application/aggregation/_iva_ledger.py`, `src/aeat/application/aggregation/__init__.py`, `src/aeat/application/aggregation/test_iva_ledger.py`.

Summary: no HIGH or CRITICAL findings were identified. The S1816 prorrata-reference carry path keeps usage-ratio and legal prorrata substrates separate, exposes no CLI business logic, and did not introduce duplicate prorrata calculators, usage-ratio shims, or prorrata CLI command surfaces in the reviewed checks.

W61.P303.S1816-001 | MEDIUM | Public prorrata calculator leaks raw Pydantic `ValidationError` for kind/period contract failures
 `compute_prorrata_general` constructs `ProrrataResult` directly at `src/aeat/domain/vat/_prorrata.py:383`; `ProrrataResult._validate_period_matches_kind` raises `ProrrataInputError` from a Pydantic model validator at `src/aeat/domain/vat/_prorrata.py:212`, but Pydantic wraps it as `pydantic_core.ValidationError`. A caller invoking `compute_prorrata_general(inputs, year=2026, kind=ProrrataKind.PROVISIONAL)` without `period` therefore receives an exception that is not an `aeat.core.errors.AeatError`, despite the public function docstring promising `ProrrataInputError` for inconsistent `kind`/`period` input. This weakens the AEAT base error boundary for public domain-service usage. The new `validate_prorrata_reference` path does catch Pydantic validation and re-raise `ProrrataInputError`, so the S1816 reference parser itself follows the expected pattern.

Verification:

- `.venv\Scripts\python.exe -m pytest src/aeat/domain/vat/test_prorrata.py src/aeat/application/aggregation/test_iva_ledger.py` passed: 57 passed.
- `.venv\Scripts\ty.exe check src/aeat/domain/vat/_prorrata.py src/aeat/domain/vat/__init__.py src/aeat/domain/vat/test_prorrata.py src/aeat/application/aggregation/_iva_ledger.py src/aeat/application/aggregation/__init__.py src/aeat/application/aggregation/test_iva_ledger.py` passed.
- `rg` checks found only the canonical definitions of `compute_prorrata_general`, `classify_input_deduction`, `is_especial_mandatory`, and `requires_sectoral_separation` under `src/aeat/domain/vat/_prorrata.py`.
- `rg` found no `usage_ratio` references in the S1816 production files reviewed.
- `rg` found no `prorrata` references under `src/aeat/entrypoints/cli`.

## Remediation Re-review 2026-05-14

W61.P303.S1816-001-REVIEW | INFO | Prior MEDIUM finding is resolved
 `compute_prorrata_general` now wraps `ProrrataResult` construction and catches Pydantic `ValidationError`, re-raising `ProrrataInputError` for invalid result windows. A runtime probe confirmed the invalid provisional-without-period call now raises `aeat.domain.vat.errors.ProrrataInputError`, and `isinstance(exc, aeat.core.errors.AeatError)` is true. The added `test_compute_general_rejects_invalid_period_with_prorrata_error` covers the public calculator path, not only direct `ProrrataResult` construction. No new HIGH or CRITICAL issues were identified in the remediation scope.

Remediation verification:

- `.venv\Scripts\python.exe -m pytest src/aeat/domain/vat/test_prorrata.py::test_compute_general_rejects_invalid_period_with_prorrata_error src/aeat/domain/vat/test_prorrata.py src/aeat/application/aggregation/test_iva_ledger.py` passed: 58 passed.
- `.venv\Scripts\ty.exe check src/aeat/domain/vat/_prorrata.py src/aeat/domain/vat/test_prorrata.py src/aeat/application/aggregation/_iva_ledger.py src/aeat/application/aggregation/test_iva_ledger.py` passed.

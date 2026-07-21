---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-01'
modified: '2026-07-17'
step_id: 'S239'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R7-MARC-D4 ledger import --period rejects 2024-1T 1T 2024/1T and 2024Q1 with Periode no reconegut

## Scope

- `works only when omitted`
- `preflight uses AAAAQN format`
- `align ledger import --period parsing with the canonical period token vocabulary established in W01.P07`
- `src/aeat/entrypoints/cli/_ledger.py`

## Description

- Ground the historical S239 testimonial against the period-grammar standardisation plan, the current `ledger import` parser, and the S294 execution record.
- Verify that production already routes `ledger import --period` through the shared strict `_optional_canonical_period` path, so no parser change is needed.
- Add real CLI dry-run coverage proving `ledger import --period 1T --year 2024` accepts the canonical AEAT token plus separate year form.
- Add real CLI refusal coverage for the historical combined forms `2024-1T`, `2024/1T`, and `2024Q1`, asserting that the refusal teaches `1T`, `0A`, and `--year`.
- Add an import-specific regression proving bare `ledger import --period 1T` refuses until the operator supplies `--year`.

## Outcome

S239 is closed as regression-only. The older testimonial expected ledger import to accept or convert several combined period spellings, but the later period-grammar standardisation superseded that with one canonical operator contract: `--period 1T --year 2024`. Calendar and hybrid spellings are now intentionally refused with AEAT-token plus `--year` guidance.

The reviewer found no issue. The only noted residual edge, import-specific bare-token-without-year refusal, was covered before closure.

## Notes

Validation:

- `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_ledger_period_grammar.py -m integration -k "import_accepts_aeat_token_with_year or import_historic_period_forms_refuse_with_current_canonical_grammar or import_period_without_year_refuses_with_year_guidance" -q -p no:cacheprovider` passed with 5 tests.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_ledger_period_grammar.py -m integration -q -p no:cacheprovider` passed with 48 tests.
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/tests/test_ledger_period_grammar.py` passed.
- `git diff --check` passed for `src/aeat/entrypoints/cli/tests/test_ledger_period_grammar.py`.

No production code changed.

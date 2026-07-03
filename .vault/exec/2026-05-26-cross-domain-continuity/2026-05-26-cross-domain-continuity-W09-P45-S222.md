---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S222'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R7-001 / W01.P03 follow-up localise ledger CSV date-parse error inner reason

## Scope

- `today wrapper text is es/ca/hu but the inner 'unsupported date format' string is English raw`
- `src/aeat/entrypoints/cli/_ledger.py`

## Description

- Ground the testimonial with `vaultspec-rag` against the financial-provider date parser, CSV row wrapper, and ledger import error wrapper.
- Promote unsupported financial-source date parse failures to a translated `FinancialValidationError` with `label`, `raw`, and `expected_format` context.
- Preserve CSV row context by resolving provider errors before embedding them in the row-level parse refusal.
- Pass source date-column labels from the CSV provider into the shared date parser.
- Add real CLI regressions for Spanish, Catalan, and Hungarian malformed CSV date import refusals.
- Review the focused patch with `vaultspec-code-reviewer`.

## Outcome

- Closed. Malformed CSV date imports under `--language es`, `--language ca`, and `--language hu` now show localized inner date-format text instead of raw English `unsupported date format`.
- Closed. The refusal keeps `CSV row 2`, the source date column label, the raw bad value, and the expected date-shape hint.
- Closed. Existing OFX and PDF provider call sites remain compatible through the date parser's default label argument.

## Notes

- The live owner was the financial-provider parser stack, not the stale plan-row pointer to `src/aeat/entrypoints/cli/_ledger.py`.
- Review found no code issues. Residual risk: invalid compact-date behavior was manually verified by the reviewer but is not covered by a dedicated committed regression; committed CLI coverage covers malformed non-compact dates across Spanish, Catalan, and Hungarian.
- Validation: `uv run --no-sync pytest src/aeat/adapters/inbound/financial/providers/tests/test_csv.py src/aeat/entrypoints/cli/tests/test_ledger_import_ux.py -q` passed with 16 selected tests and 17 deselected.
- Validation: `uv run --no-sync ruff check src/aeat/adapters/inbound/financial/providers/_base.py src/aeat/adapters/inbound/financial/providers/_csv.py src/aeat/entrypoints/cli/tests/test_ledger_import_ux.py` passed.
- Validation: `uv run --no-sync python -m aeat.locales scaffold --check` and `uv run --no-sync python -m aeat.locales audit` passed for all locales.
- Validation: reviewer ran `git diff --check` on the scoped files; only line-ending normalization warnings were emitted.

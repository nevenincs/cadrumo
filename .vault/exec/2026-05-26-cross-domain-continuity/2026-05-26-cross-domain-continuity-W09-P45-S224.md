---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S224'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R7-A fix ledger list and ledger view CliValidationBoundaryError on CSV-imported transactions

## Scope

- `LedgerTransactionPayload currency Field min_length 3 max_length 3 rejects empty or short currency strings`
- `ledger review uses LedgerReviewRow without currency and succeeds`
- `relax currency validation OR default to EUR on CSV import OR provide explicit operator-readable error pointing to the CSV currency column not config repair`
- `src/aeat/application/ledger/_actions.py`

## Description

- Ground the testimonial with `vaultspec-rag` against the ledger CSV import, read payload, and list/view validation surfaces.
- Trace the live path through `CsvProvider._parse_tabular_transaction_row`, `build_raw_transaction`, and `RawTransaction`.
- Preserve the existing missing-currency and blank-currency default to the configured default currency.
- Reject nonblank malformed currency cells at the CSV provider boundary with row, column, and bad-value context.
- Add provider and real CLI regressions for defaulted currency and malformed short currency.
- Review the focused patch with `vaultspec-code-reviewer`.

## Outcome

- Closed. CSV rows with no currency column or a blank currency cell import with the default currency and `ledger list` / `ledger view` serialize the row successfully.
- Closed. CSV rows with a short nonblank currency such as `EU` now fail during `ledger import` with `CSV row 2`, `currency column`, and the bad value in the refusal, before any `LedgerTransactionPayload` validation path can suggest `aeat config repair`.
- Closed. `RawTransaction.currency` and `LedgerTransactionPayload.currency` remain strict three-letter fields; the fix moved invalid input rejection earlier rather than relaxing the read contract.

## Notes

- The live owner was `src/aeat/adapters/inbound/financial/providers/_csv.py`, not the stale plan-row pointer to `src/aeat/application/ledger/_actions.py`.
- Review found no code issues. Residual risk: the provider-level currency detail is English text embedded inside the localized ledger-import wrapper, matching existing provider diagnostics but leaving mixed-language output for this specific malformed-source reason.
- Validation: `uv run --no-sync pytest src/aeat/adapters/inbound/financial/providers/tests/test_csv.py -q` passed with 16 tests.
- Validation: `uv run --no-sync pytest -m integration src/aeat/entrypoints/cli/tests/test_ledger_import_ux.py::test_missing_or_blank_csv_currency_imports_as_default_and_list_view_succeed src/aeat/entrypoints/cli/tests/test_ledger_import_ux.py::test_short_csv_currency_refuses_at_import_with_currency_column_message -q` passed with 3 tests.
- Validation: `uv run --no-sync ruff check src/aeat/adapters/inbound/financial/providers/_csv.py src/aeat/adapters/inbound/financial/providers/tests/test_csv.py src/aeat/entrypoints/cli/tests/test_ledger_import_ux.py` passed.
- Validation: `git diff --check` passed for the three S224 files.
- Note: full `test_ledger_import_ux.py` was not green because pre-existing OFX parsing test `test_cross_format_import_of_the_same_movements_deduplicates` failed with `could not parse OFX file: <input-ofx>`; no OFX code was touched.

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

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cross-domain-continuity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S224 and 2026-05-26-cross-domain-continuity-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The R7-A fix ledger list and ledger view CliValidationBoundaryError on CSV-imported transactions and ## Scope

- `LedgerTransactionPayload currency Field min_length 3 max_length 3 rejects empty or short currency strings`
- `ledger review uses LedgerReviewRow without currency and succeeds`
- `relax currency validation OR default to EUR on CSV import OR provide explicit operator-readable error pointing to the CSV currency column not config repair`
- `src/aeat/application/ledger/_actions.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# R7-A fix ledger list and ledger view CliValidationBoundaryError on CSV-imported transactions

## Scope

- `LedgerTransactionPayload currency Field min_length 3 max_length 3 rejects empty or short currency strings`
- `ledger review uses LedgerReviewRow without currency and succeeds`
- `relax currency validation OR default to EUR on CSV import OR provide explicit operator-readable error pointing to the CSV currency column not config repair`
- `src/aeat/application/ledger/_actions.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

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

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

- The live owner was `src/aeat/adapters/inbound/financial/providers/_csv.py`, not the stale plan-row pointer to `src/aeat/application/ledger/_actions.py`.
- Review found no code issues. Residual risk: the provider-level currency detail is English text embedded inside the localized ledger-import wrapper, matching existing provider diagnostics but leaving mixed-language output for this specific malformed-source reason.
- Validation: `uv run --no-sync pytest src/aeat/adapters/inbound/financial/providers/tests/test_csv.py -q` passed with 16 tests.
- Validation: `uv run --no-sync pytest -m integration src/aeat/entrypoints/cli/tests/test_ledger_import_ux.py::test_missing_or_blank_csv_currency_imports_as_default_and_list_view_succeed src/aeat/entrypoints/cli/tests/test_ledger_import_ux.py::test_short_csv_currency_refuses_at_import_with_currency_column_message -q` passed with 3 tests.
- Validation: `uv run --no-sync ruff check src/aeat/adapters/inbound/financial/providers/_csv.py src/aeat/adapters/inbound/financial/providers/tests/test_csv.py src/aeat/entrypoints/cli/tests/test_ledger_import_ux.py` passed.
- Validation: `git diff --check` passed for the three S224 files.
- Note: full `test_ledger_import_ux.py` was not green because pre-existing OFX parsing test `test_cross_format_import_of_the_same_movements_deduplicates` failed with `could not parse OFX file: <input-ofx>`; no OFX code was touched.

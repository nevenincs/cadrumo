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

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cross-domain-continuity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S222 and 2026-05-26-cross-domain-continuity-plan placeholders are machine-filled by
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
     The R7-001 / W01.P03 follow-up localise ledger CSV date-parse error inner reason and ## Scope

- `today wrapper text is es/ca/hu but the inner 'unsupported date format' string is English raw`
- `src/aeat/entrypoints/cli/_ledger.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# R7-001 / W01.P03 follow-up localise ledger CSV date-parse error inner reason

## Scope

- `today wrapper text is es/ca/hu but the inner 'unsupported date format' string is English raw`
- `src/aeat/entrypoints/cli/_ledger.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

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

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

- The live owner was the financial-provider parser stack, not the stale plan-row pointer to `src/aeat/entrypoints/cli/_ledger.py`.
- Review found no code issues. Residual risk: invalid compact-date behavior was manually verified by the reviewer but is not covered by a dedicated committed regression; committed CLI coverage covers malformed non-compact dates across Spanish, Catalan, and Hungarian.
- Validation: `uv run --no-sync pytest src/aeat/adapters/inbound/financial/providers/tests/test_csv.py src/aeat/entrypoints/cli/tests/test_ledger_import_ux.py -q` passed with 16 selected tests and 17 deselected.
- Validation: `uv run --no-sync ruff check src/aeat/adapters/inbound/financial/providers/_base.py src/aeat/adapters/inbound/financial/providers/_csv.py src/aeat/entrypoints/cli/tests/test_ledger_import_ux.py` passed.
- Validation: `uv run --no-sync python -m aeat.locales scaffold --check` and `uv run --no-sync python -m aeat.locales audit` passed for all locales.
- Validation: reviewer ran `git diff --check` on the scoped files; only line-ending normalization warnings were emitted.

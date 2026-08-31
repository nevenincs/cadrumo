---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:006cbc7904a1d39225f8802cbe248bbe07ee0131d6ba0de2b7d9b6544369be79'
step_id: 'S202'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in `test_record_design.py` into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_record_design.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/tests/test_record_design.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_record_design_layout.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_record_design_narrative.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_record_design_pdf.py`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S202.md`
- `A` `.vault/audit/2026-08-31-ci-lane-deconflation-p05-s202-execution-self-review-audit.md`
- `verify:` `git show --check 2bd1f782b5a6e4064386624ad0f8023500f62f12` -> `pass`

## Notes

- Source provenance is `2bd1f782b5a6e4064386624ad0f8023500f62f12`, whose manifest is exactly the four source paths above. Raw physical blob counts are 582 lines for `test_record_design.py`, 533 for `test_record_design_layout.py`, 425 for `test_record_design_narrative.py`, and 434 for `test_record_design_pdf.py`; none crosses the 1250-line ceiling. Its four-path manifest contains no threshold or baseline file.
- Formal AST review found 53 top-level definitions and 51 test definitions preserved with no missing, extra, or duplicate definitions; targeted import search found no imports from the old test module into a new sibling.
- The executor reported that the focused four-module pytest family passed 82 tests in 138.58 seconds with four known `openpyxl` conditional-format warnings, and reported passing Ruff check/format and `compileall`. Those are executor-reported receipts, not newly reproduced command transcripts in this record.
- The executor also reported a non-mutating global size scan with 57 unrelated findings and nonzero status; no S202 sibling appeared. This is not a repository-wide green result, and no baseline, threshold, `--write-baseline`, or `--accept-growth` action was taken.

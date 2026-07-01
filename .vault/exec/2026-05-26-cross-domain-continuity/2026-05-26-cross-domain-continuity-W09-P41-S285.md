---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-01'
modified: '2026-07-01'
step_id: 'S285'
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
     The S285 and 2026-05-26-cross-domain-continuity-plan placeholders are machine-filled by
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
     The TAUTOLOGICAL_TEST_SUSPICION sweep S98 follow-up: refactor test_cross_dependency_calculations.py M180 and M190 tests to derive expected values from AEAT workbook or grounded fixture instead of synthetic Decimal hand-computed oracles and ## Scope

- `per no-tautological-calculation-tests rule`
- `src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# TAUTOLOGICAL_TEST_SUSPICION sweep S98 follow-up: refactor test_cross_dependency_calculations.py M180 and M190 tests to derive expected values from AEAT workbook or grounded fixture instead of synthetic Decimal hand-computed oracles

## Scope

- `per no-tautological-calculation-tests rule`
- `src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py`

## Description

- Ground the test-refactor scope with `uvx vaultspec-rag search "test_cross_dependency_calculations M180 M190 tautological expected AEAT workbook grounded fixture" --type code`.
- Replace M180 annual summary expected values with values parsed from bundled `justificantes/180/2024-0A.pdf` and checked against its sidecar provenance.
- Replace M190 relation and binding expected values with values parsed from bundled `justificantes/190/2024-0A.pdf`, including detail-row grounding for the G/01 perceptor.
- Shape quarterly source observations to sum to the fixture annual totals without using the same hand-computed Decimal literals as the expected oracle.
- Add explicit zero defaults for the two Madrid family-profile bindings now required by the M100 2025 revision so the unrelated M100 cross-dependency scenarios continue to exercise their payment and relation paths.
- Run an independent code review persona against the patch and close with no findings.

## Outcome

Closed. M180 and M190 expected totals no longer come from synthetic hand-computed Decimal oracle literals in the test body; they are parsed from bundled PDF fixture surfaces and guarded by sidecar provenance checks. The M100 fixture-input drift was resolved inside the same test file by supplying the same fail-closed zero profile defaults used by the real profile binding layer for non-applicable Madrid family deduction branches.

Validation passed:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/tests/test_cross_dependency_calculations.py -q -p no:cacheprovider` -> 13 passed.
- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/tests/test_cross_dependency_calculations.py` -> passed.
- `git diff --check -- src/aeat/domain/calculations/registry/tests/test_cross_dependency_calculations.py` -> passed.
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-26-cross-domain-continuity-plan.md` -> passed with the existing `PLAN022` monotonic-order warning.

## Notes

The first full-file test run failed outside the M180/M190 refactor because newer M100 2025 formulas require `renta-2025-profile-unidad-familiar-otros-miembros-base` and `renta-2025-profile-madrid-nacimiento-adopcion-eligible-count`. Supplying explicit zero binding values preserves the original M100 test intent and mirrors the real profile resolver's defaulting behavior.

---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:a18dc602a200aa2598fc6a4a6782a0c91e2cf88e8f35d03fcb30b949f55d3187'
step_id: 'S13'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace registry-temporal-coverage with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S13 and 2026-08-14-registry-temporal-coverage-plan placeholders are machine-filled by
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
     The Replace the single-representative-year assessment with a derived modelo, filing-year, period and schema-family matrix over the validated authority that assesses every claimed year up to the assessment horizon, proven by property on a real long-span open revision and ## Scope

- `src/cadrumo/domain/calculations/registry/_coverage.py`
- `src/cadrumo/domain/calculations/registry/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Replace the single-representative-year assessment with a derived modelo, filing-year, period and schema-family matrix over the validated authority that assesses every claimed year up to the assessment horizon, proven by property on a real long-span open revision

## Scope

- `src/cadrumo/domain/calculations/registry/_coverage.py`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Derive all selector cells from `revision_selection_coordinates` and the registry-supported filing-year horizon.
- Re-run law selection and the grade boundary per cell; retain every refusal and aggregate revision-facing views without overwriting later cells.
- Traverse every coordinate in construct-evidence and filing-export coverage consumers, retaining canonical period tokens without alias expansion.
- Add real long-span, later-cell, horizon, and period-alias mutation coverage; the current authority derives 2,220 cells across 102 revisions without an encoded count assertion.
- Keep applicability and calculation-grade revisions inspection-only in the evidence audit; only filing-grade revisions may claim filing-scope evidence.

## Outcome

The representative-coordinate path is retired. Coverage is derived from validated authority and selector law for every claimed filing-year/period cell through the supported-year horizon. Commit `915a66a5bc` carries the mixed-main implementation provenance; this step record carries the remaining scope correction and verification evidence.

Focused gates passed: scoped Ruff; temporal coverage 39 passed; full matrix property passed; model-law coverage property passed; construct-evidence checks 5 passed; conformance projection checks 29 passed.

## Notes

No data loss or registry authoring changes. The filing emitted-byte integration lane has one stale M353 expectation: it expects a filing-layout refusal, but both the historical first cell and the full matrix reach the existing production-emission-proof refusal. It is unrelated to S13 and remains outside this step.

The derived inputs for the pending source-era rows are now exact and selector-owned: M038 (2002 through 2026, months 01–12); M182 (2007 through 2026, 0A); M187, M188 and M194 (2019 through 2026, 0A); M220 (2024 plus 2025 through 2026, 0A); M721 (2023 through 2026, 0A); and M763 (2011 through 2026, quarters 1T–4T). These are matrix worklist inputs, not authority promotions or hand-written period lists.

Independent review is scheduled separately by the parent coordinator; its audit scaffold is intentionally excluded from this implementation commit.

---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:f3e7deace052e7e8cd703d34aafc0e748576762a15003547770f0adb7f70bf6e'
step_id: 'S42'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace registry-completeness-closure with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S42 and 2026-08-24-registry-completeness-closure-plan placeholders are machine-filled by
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
     The Constrain temporal evidence identity, period, and filing-year fields to registry semantics and add mutation proof for every composer refusal outcome and ## Scope

- `src/cadrumo/application/registry/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Constrain temporal evidence identity, period, and filing-year fields to registry semantics and add mutation proof for every composer refusal outcome

## Scope

- `src/cadrumo/application/registry/`

## Description

- Replace raw temporal evidence coordinates with the canonical registry identifier and selector-period annotations, and align the filing-year range with snapshot coordinates.
- Preserve law-selection snapshot errors as the declared `law_selection_refused` denominator row.
- Add public-boundary rejection coverage for fabricated modelo, revision, selected-revision, period, and filing-year values.
- Mutate real bundled authorities and cached snapshots to prove each composer refusal preserves one actionable report row.

## Outcome

`TemporalRevisionCoverage` now carries registry-constrained identity and period values and cannot represent an out-of-window filing year. The composer records, rather than raises, no-selection errors; all five declared refusal codes have a mutation-backed regression proof.

Verification passed: `uv run --no-sync ruff check` on the two changed Python files; focused Pydantic coordinate tests (5 passed); and a direct real-authority probe covering `law_selection_refused`, `selected_revision_mismatch`, `undeclared_authority_grade`, `declared_grade_snapshot_refused`, and `snapshot_revision_mismatch`.

## Notes

`ruff format --check` reports an existing comprehension reflow in `test_temporal_coverage.py` outside this Step's edits; it was left unchanged to preserve shared-worktree ownership.

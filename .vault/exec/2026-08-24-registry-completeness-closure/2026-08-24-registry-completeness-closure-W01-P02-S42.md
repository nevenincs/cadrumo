---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:f8a29123f025525014899fd0dd326169b2c88abbedbaf3dad514cd653f0aa5e6'
step_id: 'S42'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

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

---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:bc9dd8e9c1410572faf541cf7210710d1706a998a600eec85d85e5ccbab707fb'
step_id: 'S01'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# Extend the existing validated source catalogue with hash-pinned binary selection and reject inapplicable or drifting sources

## Scope

- `src/cadrumo/_data/registry/aeat/legal/is.toml`

## Description

- Extend `SourceReference` with optional, record-design-only epoch metadata.
- Add `resolve_record_design_binary` at the existing corpus-catalogue authority boundary.
- Pin the bundled Modelo 200 2024 and 2025 design epochs in the shared source catalogue.
- Exercise successful selection, year refusal, hash drift, and missing-epoch refusal against the real bundled corpus.

## Outcome

The catalogue now supplies an authored design epoch for the Modelo 200 binaries and the resolver refuses undeclared, wrong-kind, blank-epoch, epoch-mismatching, year-inapplicable, missing-applicability, missing, byte-drifting, or hash-drifting selections before a parser receives a path. It returns only the verified bundled binary path and its typed source reference.

## Verification

`uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_record_design_source_selection.py -q`

`4 passed in 14.86s`

`uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_catalogue_verification.py -q`

`22 passed in 16.48s`

`uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/_schema_references.py src/cadrumo/domain/calculations/registry/_corpus_catalogue.py src/cadrumo/domain/calculations/registry/tests/test_record_design_source_selection.py`

`All checks passed!`

`uv run --no-sync basedpyright src/cadrumo/domain/calculations/registry/_schema_references.py src/cadrumo/domain/calculations/registry/_corpus_catalogue.py src/cadrumo/domain/calculations/registry/tests/test_record_design_source_selection.py`

`0 errors, 0 warnings, 0 notes`

## Notes

The selector intentionally does not infer a source or an epoch from filenames, revisions, or existing export fragments. Later semantic-map and generation steps must provide the explicitly authored source reference and epoch.

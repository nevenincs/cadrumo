---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:b005f1c208ce949149c6ab34fcf315ae804f1c53d6acac2bc036b2d2da462d68'
step_id: 'S02'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Define the typed intermediate representation with complete source anchors, coordinates, validation metadata, and declared totals

## Scope

- `dev/registry/`

## Description

- Select the hash-pinned official record-design binary through the S01 source-catalogue resolver.
- Project the shipped parser output into frozen source, sheet, and field intermediate models.
- Retain exact source hashes, formats, epochs, parser anchors, coordinates, metadata, and declared totals without a second parser or extracted derivative input.
- Expose the resolver and resolved-binary type through the owning registry facade.
- Prove the projection against the real Modelo 200 2025 official workbook and complete independent review.

## Outcome

The development-only IR is now the fail-closed typed handoff from a verified official binary and shipped parser output to later semantic-map and generator steps. It rejects missing source authority, unsupported formats, empty parser output, empty sheets, and duplicate record identities.

## Notes

- `uv run --no-sync pytest dev/registry/tests/test_record_design_ir.py -q` passed: 1 test.
- `uv run --no-sync ruff check dev/registry/_record_design_ir.py dev/registry/tests/test_record_design_ir.py` passed.
- `uv run --no-sync basedpyright dev/registry/_record_design_ir.py dev/registry/tests/test_record_design_ir.py` reported 0 errors, warnings, and notes.
- Independent review found no unresolved critical, high, or medium issue. The registry facade's single `__all__` ordering warning predates S02 and remains outside this Step.

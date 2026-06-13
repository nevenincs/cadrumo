---
tags:
  - '#audit'
  - '#registry-record-design-boundary'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---

# `registry-record-design-boundary` audit: `record design extraction boundary audit`

## Scope

Audited `src/aeat/domain/calculations/registry/_record_design.py` as a
large registry production module that mixes official Diseño de Registro
source parsing with registry completeness and coverage derivation.

## Findings

### High

- `_record_design.py` is 1,755 working-tree lines and combines public
  record-design models, file dispatch, workbook extraction, XLS
  extraction, PDF text extraction, PDF visual-chart extraction,
  calculation-closure derivation, completeness-manifest derivation, and
  Diseño coverage reporting.
- The current working tree contains formatting-only peer WIP in the
  calculation-closure/completeness region. This slice must not edit
  production code.
- `src/aeat/domain/calculations/registry/__init__.py` re-exports the
  public record-design API, and `test_public_api_boundaries.py` treats
  `_record_design` as a private module. Extraction must preserve
  `aeat.domain.calculations.registry` imports and keep `_record_design.py`
  as the compatibility facade.

### Medium

- Workbook and XLS extraction form a cohesive parser family that can move
  behind the facade without changing public behavior.
- PDF text extraction and visual chart extraction are tightly coupled by
  page snapshots, rect/word structures, and fallback parsing order. They
  should move together initially rather than being split into tiny helper
  modules.
- Calculation closure, completeness derivation, and coverage reporting
  form a separate registry-derivation family. This family depends on
  `ModeloRevision` and parsed `RecordDesignSheet` data but does not need
  PDF/workbook parser internals.
- `extract_record_design` should remain in `_record_design.py` during the
  first split because it is the public dispatcher and cache boundary for
  source paths.

### Low

- `RecordDesignField`, `RecordDesignSheet`, and `DerivedDisenoCasilla`
  are small shared data models. They can either remain in the facade
  until all parser families move or be moved first to a small model
  module with compatibility re-exports.

## Recommendations

1. Keep `_record_design.py` as a compatibility facade and public
   dispatcher.
2. Move record-design data models first only if it simplifies parser
   imports; otherwise leave them in the facade until parser extraction is
   complete.
3. Extract workbook and XLS parsing into a private parser module. Preserve
   `extract_record_design_workbook` and `extract_record_design_xls_workbook`
   as facade re-exports.
4. Extract PDF parsing as one private module that owns both text parsing
   and visual-chart fallback parsing. Do not split visual-chart helpers
   independently in the first pass.
5. Extract calculation closure, completeness derivation, and coverage
   reporting into a private derivation module after parser extraction or
   after the active peer formatting WIP lands.
6. Preserve the `extract_record_design` dispatcher and cache key behavior
   exactly.
7. For each extraction commit, run `test_record_design.py`,
   `test_public_api_boundaries.py`, and affected model-specific registry
   tests that assert record-design parsing or Diseño coverage.

## Codification candidates

- **Source:** finding High-1.
  **Rule slug:** `registry-record-design-parser-facade`.
  **Rule:** Record-design parser decomposition must preserve the facade
  dispatcher and move parser families behind compatibility re-exports.

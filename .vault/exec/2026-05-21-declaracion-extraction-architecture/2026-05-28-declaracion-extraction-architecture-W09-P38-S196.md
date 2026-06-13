---
step_id: S196
tags:
  - "#exec"
  - "#declaracion-extraction-architecture"
date: '2026-05-28'
modified: '2026-05-28'
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-21-declaracion-extraction-architecture-adr]]"
---

# declaracion-extraction-architecture W09.P38.S196 — bbox_anchored extraction strategy: schema + parser + profiles + tests + validator

## Outcome

Commit `ad285e970`. All 99 parser boundary tests pass. Pyright 0 errors.

## Problem

M130, M111, and M131 print box numbers at the right side of the table row (line-end), not at line-start. The existing `numeric_casilla` strategy splits text by line and requires the box number at the start of the line, so it extracted 0 casillas from all three modelos — producing gap tests that confirmed zero coverage. The W02 ADR named `bbox_anchored` as the future solution; this step implements it.

## Actions

### UNIT 1 — Schema extension (`_schema.py`, `__init__.py`)

Added `BboxAnchorSpec(RegistryModel)` with six fields: `box_number_pattern: str`, `value_offset: Literal["left_of_number","above_number","right_of_number"]`, `anchor_x_min/max: float | None`, `value_x_max: float | None`, `column_anchor: str | None`. Strict frozen extra=forbid consistent with `RegistryModel`.

Extended `ExtractionTargetDefinition.match_strategy` Literal to include `"bbox_anchored"`. Added `bbox_anchor: BboxAnchorSpec | None = None`. Added `@model_validator(mode="after")` enforcing: named_label requires label_pattern; numeric_casilla forbids label_pattern; bbox_anchored requires bbox_anchor; non-bbox_anchored forbids bbox_anchor. Exported `BboxAnchorSpec` from `registry/__init__.py`.

### UNIT 2 — Parser branch (`_parser.py`)

Added `_extract_pages_words(pdf_path)` using `pdfplumber.open()` — lazy load triggered only when a `bbox_anchored` target is present in the profile. Prevents pdfplumber overhead for numeric/named profiles.

Added `_find_bbox_casilla_hits(words, target)` with:
- `_BBOX_Y_TOLERANCE = 3.0` pts for same-row matching
- `_BBOX_X_GAP_TOLERANCE = 150.0` pts for right-of-number search
- `anchor_x_min/anchor_x_max` filtering to isolate right-column box numbers from inline formula references
- `value_x_max` upper bound to prevent col-A empty cells from matching col-B box numbers
- `_resolve_value_word(words, anchor_word, value_offset, *, value_x_max=None)` for `right_of_number` resolution

Updated `_extract_profile_values` to collect `bbox_anchored` targets separately and call `_find_bbox_casilla_hits`. Updated coverage error condition: `if ambiguous or malformed or coverage < profile.min_coverage` — `missing` alone no longer raises (required for partial AEAT filings where zero/not-applicable casillas are legitimately absent).

### UNIT 3 — M130 profile conversion

19 targets → `bbox_anchored` with `anchor_x_min=450.0, anchor_x_max=480.0, value_offset="right_of_number"`. M130 layout: box numbers at x0~464 (right column), values at x0~533-545 on the same y-row. Inline formula references contain two-digit numbers at x0~109-200; the x-anchor isolates the right column. `min_coverage="0"`, `corpus_round_trip_verified=true`, `verification_source="real_aeat_corpus_pdf"`.

### UNIT 4 — M111 profile conversion

29 targets (casilla 29 excluded — not a numeric casilla) in 3 column groups:
- Col A (01,04,07,10,13,16,19,22,25): `anchor_x_min=250, anchor_x_max=290, value_x_max=345`
- Col B (02,05,08,11,14,17,20,23,26): `anchor_x_min=330, anchor_x_max=370, value_x_max=459`
- Col C (03,06,09,12,15,18,21,24,27,28,30): `anchor_x_min=450, anchor_x_max=490` (no value_x_max)

`value_x_max` prevents col-A empty cells from matching the adjacent col-B box number (~75 pts away). `min_coverage="0"`, `corpus_round_trip_verified=true`, `verification_source="real_aeat_corpus_pdf"`.

### UNIT 5 — M131 2026 profile conversion

15 targets → `bbox_anchored` with no x-constraints (single box per row, varying x0 215-309, value immediately to the right). `corpus_round_trip_verified=true`, `verification_source="synthetic_from_aeat_published_text"`.

### UNIT 6 — Test rewrites (`test_parser_boundary.py`)

Replaced all three gap tests with real roundtrip tests:

**M130** (`test_parser_extracts_modelo_130_casillas_from_corpus`): 15 corpus PDFs × ground-truth Decimal values from pdfplumber probe. Representative ground truth: 2022-2T → {01,02,03,04,05,06,07,12,14,17,19} = Decimal("1000.00").

**M111** (`test_parser_extracts_modelo_111_casillas_from_corpus`): real corpus PDF (2021-4T), asserts casillas 07=Decimal("1000.00"), 08/09 extracted, 28/30 extracted for negative filing.

**M131** (`test_parser_extracts_modelo_131_casillas_from_synthetic_fixture`): synthetic 2024-1T.pdf, all 15 casillas. Ground truth: 01=Decimal("5000.00"), 02/07/10/13/15=Decimal("100.00"), rest=Decimal("0.00").

Updated `test_parser_fails_when_registry_profile_targets_are_missing`: injects a `min_coverage=Decimal("1")` strict snapshot via `model_copy` on a real corpus PDF to confirm the error path is reachable.

Updated `test_real_redacted_declaration_copy_extracts_partial_casillas`: the 2024-1T redacted PDF now successfully extracts casillas 02/03/19 — test renamed and assertions flipped to confirm success.

### UNIT 7 — Snapshot-level validator (`_validate_extraction_profiles.py`, `_validate_record_sections.py`)

Added `validate_bbox_anchor_consistency(scope, target)` function: errors if `bbox_anchored` target has no `bbox_anchor`, or if non-bbox target carries a `bbox_anchor`. Wired into `validate_extraction_profile_section` loop in `_validate_record_sections.py`.

### ADR amendment not written as separate file

The ADR amendment covering the `bbox_anchored` design is implicitly recorded via this step record and the plan W09 wave intent block.

## Verification

```
pytest src/aeat/adapters/inbound/declaracion/test_parser_boundary.py
# 99 passed in 226.64s
```

```
pyright src/aeat/adapters/inbound/declaracion/_parser.py
src/aeat/domain/calculations/registry/_schema.py
# 0 errors, 2 pre-existing warnings (private member usage in _validate_record_sections.py)
```

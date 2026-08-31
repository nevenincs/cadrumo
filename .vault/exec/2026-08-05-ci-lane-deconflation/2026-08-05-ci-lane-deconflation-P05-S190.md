---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:f5d2e7a24852b9f287f28d787e47947682d834f4c9b54e994cbfbfdb9d7f5a4c'
step_id: 'S190'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Refactor the size-budget subjects in record_design.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/domain/calculations/registry/record_design.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/record_design.py`
- `M` `src/cadrumo/domain/calculations/registry/record_design_coverage.py`
- `M` `src/cadrumo/domain/calculations/registry/_validate_export_layout_coverage.py`
- `A` `src/cadrumo/domain/calculations/registry/record_design_layout_markers.py`
- `A` `src/cadrumo/domain/calculations/registry/record_design_pdf_orchestration.py`
- `A` `src/cadrumo/domain/calculations/registry/record_design_pdf_repairs.py`
- `A` `src/cadrumo/domain/calculations/registry/record_design_pdf_rows.py`
- `A` `src/cadrumo/domain/calculations/registry/record_design_pdf_state.py`
- `A` `src/cadrumo/domain/calculations/registry/record_design_pdf_visual.py`
- `A` `src/cadrumo/domain/calculations/registry/record_design_sources.py`
- `A` `src/cadrumo/domain/calculations/registry/record_design_workbook.py`
- `A` `src/cadrumo/domain/calculations/registry/record_design_workbook_headers.py`
- `M` `dev/registry/pipeline/_render_profile.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_diagram_design_band_recovery_baseline.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_every_bundled_design_is_read_or_reported.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_modelo_185_historical_annex.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_record_design.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_record_design_bare_coordinate_rejoin.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_record_design_bracketed_payload.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_record_design_coordinate_stutter_recovery.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_record_design_double_struck.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_record_design_glued_naturaleza_split.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_record_design_glued_ordinal.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_record_design_headless_tail.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_record_design_identity_recovery.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_record_design_naturaleza_tokens.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_record_design_page_record_extractor_choice.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_record_design_page_token.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_record_design_reversed_columns.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_record_design_row_marker.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_record_design_row_punctuation.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_record_design_stranded_casilla_tags.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_record_design_truncated_offset_repair.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_record_design_wrapped_description.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_revision_span_matches_published_designs.py`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S190.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_record_design_identity_recovery.py src/cadrumo/domain/calculations/registry/tests/test_record_design_bracketed_payload.py -q` -> `pass` (13 passed in 3.53s)
- `verify:` targeted `ruff check`, `ruff format --check`, runtime-import/DAG, and `git diff --check` probes -> `pass`

## Notes

- The canonical surface remains `record_design.py`; it owns the public `extract_record_design*` contract and delegates implementation to cohesive private siblings. There is no facade or re-export compatibility layer.
- Measured modules are all below the unchanged 1,250-line policy: primary 254; coverage 861; layout markers 36; PDF orchestration 297; PDF repairs 974; PDF rows 592; PDF state 1,043; PDF visual 430; sources 211; workbook 784; workbook headers 378. The largest measured production callable in the changed family is `derive_calculation_completeness_casillas` at 136 lines, below the unchanged 180-line limit. No baseline or threshold file is part of this Step.
- The global `python -m dev.audit.size_budget` scan reported 64 pre-existing out-of-scope findings; none names a changed `record_design*` production module or callable. This record does not claim that global audit is green.
- The earlier direct-consumer risk was resolved before receipt: `ABSENT_NATURALEZA_TYPE_CODE` has one semantic owner in `record_design_pdf_rows.py`; `dev/registry/pipeline/_render_profile.py` imports that owner, and its runtime import passed. The runtime sibling import graph is acyclic.
- Resource relocation was co-located with private-import moves in eleven working-tree files. The S190 source commit uses an isolated temporary index that retains the resource changes outside this Step and stages only the explicitly reviewed import moves.
- The focused 13-pass receipt above is the only pytest receipt claimed. A broader/core `test_record_design.py` attempt produced no final receipt and is deliberately not represented as passed.

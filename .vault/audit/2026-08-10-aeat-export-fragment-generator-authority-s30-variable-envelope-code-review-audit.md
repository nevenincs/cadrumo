---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:9b5796ea2c62a7867a696ecaff87e16afa351122988b07923ccd893004efb7ef'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# `aeat-export-fragment-generator-authority` audit: `S30 variable envelope code review`

## Scope

Reviewed current HEAD `727cff8e85` against the amended authority ADR, the S08 authority-gap research, plan row `W01.P01.S30`, its execution record, and the S30 payload recorded across commits `0316ec8f58`, `38d9447750`, `4aafa285c1`, `e2b4ecf15a`, and `727cff8e85`. The review covered exact `Total`/`Total:` cached-positive-integer recovery, fixed and envelope geometry, lossless typed `DP200000` projection and malformed refusal, fixed/variable IR separation, semantic-join and rendering boundaries, schema-version propagation, public-facade ownership, absence of compatibility shims, real-source test independence, and vault traceability.

Independent verification ran the parser, IR, and source-boundary files with 18 passing tests and two upstream `openpyxl` warnings; scoped Ruff and BasedPyright passed. A direct temporary-workbook probe demonstrated accepted fixed gaps, fixed overlaps, and an overlapping `DP200000` prefix. The provenance-manifest test file failed with one failure and three passes because its fixture still records parser schema version 1 while the production contract now requires version 2.

## Findings

### s30-variable-envelope-code-review | low | malformed-envelope negative coverage is too thin

`src/cadrumo/domain/calculations/registry/tests/test_record_design.py` exercises only a duplicate relative suffix. The production parser also contains refusal branches for duplicate bodies, duplicate fixed and variable totals, mixed fixed/variable totals, incomplete markers, wrong body offset, and marker-order defects, but no focused test proves those branches bite. This is the same residual risk acknowledged by the S30 execution record and leaves later refactors able to weaken malformed-composition refusal without a red gate.

### s30-variable-envelope-code-review | medium | terminal extent is not a complete geometry proof

`src/cadrumo/domain/calculations/registry/_record_design.py` computes `terminal_extent` with `max(offset + length - 1)` and checks only that maximum against a fixed total or that the variable body begins one byte later. It does not require the first fixed field to start at one or each subsequent field to start immediately after the previous field. Independent temporary-workbook probes confirmed that a fixed overlap, a fixed gap, and an overlapping `DP200000` prefix are all accepted and projected. The later fixed-record renderer has a stronger contiguity check, but variable envelopes are deliberately outside that renderer and therefore lack the separately proven composition geometry required by the ADR.

### s30-variable-envelope-code-review | high | semantic join drops the variable-envelope proof boundary

`dev/registry/_record_design_ir.py` preserves `variable_envelopes`, but `dev/registry/_semantic_map_validation.py` validates bijection only over `intermediate.sheets`, `dev/registry/_semantic_map_join.py` builds `JoinedRecordDesign` with only fixed records and fields, and `dev/registry/_export_tree.py` accepts that joined value without envelope or composition-proof state. Current HEAD therefore allows a design containing `DP200000` to advance into complete fixed-tree rendering after the typed envelope has been silently discarded. This contradicts the amended ADR requirement to block generation until the separate envelope contract and composition proof pass, and no test proves such generation is refused.

### s30-variable-envelope-code-review | high | parser schema version two leaves the provenance contract gate red

S30 advances `RECORD_DESIGN_INTERMEDIATE_SCHEMA_VERSION` to 2, and production provenance validation correctly requires that value. However, `dev/registry/tests/test_provenance_manifest.py` still constructs its canonical manifest with `parser_schema_version=1` and explicitly treats version 2 as drift. Running that test file on current HEAD produced one failure and three passes before the intended legacy-shape assertions could execute. The schema transition is therefore not integrated across its direct contract tests, contrary to the S30 execution record's completed-gate claim.

## Recommendations

- Add parameterized malformed-workbook tests for every parser refusal branch, including duplicate, mixed, incomplete, offset, and ordering defects.
- Centralize exact fixed-field geometry validation for workbook and PDF paths: positive coordinates, first offset one, strict source-order ordinals, and contiguous non-overlapping offsets. Apply the same validator to the `DP200000` prefix before constructing its envelope.
- Carry typed envelope state, or a source-bound typed composition-proof result, through semantic validation and `JoinedRecordDesign`; make `render_complete_export_tree` refuse any design containing an unproved envelope before creating the target directory. Add a real Modelo 200 source test and an adversarial proof-state mutation test.
- Update provenance fixtures and drift assertions to derive the current parser schema version from `RECORD_DESIGN_INTERMEDIATE_SCHEMA_VERSION`, assert version 1 is rejected, and rerun the complete provenance, parser, IR, join, and renderer boundary suite.
- Keep `W01.P01.S30` open or reopen it until both HIGH findings and the MEDIUM geometry finding are resolved and independently re-reviewed. No PASS is recorded while those findings remain unresolved.

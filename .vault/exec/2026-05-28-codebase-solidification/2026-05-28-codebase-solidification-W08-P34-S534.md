---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: 'S534'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W08.P34.S534`

INTRODUCE: `RowSetGroupingKind(StrEnum)` in `aeat.core.aggregation`; migrate dispatch dict, if-chain comparisons in `_row_set_assembly.py`, and selector dispatch in `_bindings.py` from bare strings to enum members.

- Modified: `src/aeat/core/aggregation.py` (added `RowSetGroupingKind`)
- Modified: `src/aeat/application/calculations/_row_set_assembly.py` (dispatch dict + if-chain)
- Modified: `src/aeat/domain/calculations/registry/_bindings.py` (4 comparison sites + dispatch dict)
- Modified: `src/aeat/domain/calculations/registry/_schema.py` (import added)

## Description

`RowSetGroupingKind` members: `WITHHOLDING = "withholding"`, `RELATED_PARTY = "related_party"`, `FOREIGN_ASSET = "foreign_asset"`, `ATRIBUCION = "atribucion"`, `REFUND = "refund"`. Three schema Literal values (`"related_party_operation"`, `"atribucion_member"`, `"refund_operation"`) differ from the StrEnum values and were intentionally left as bare strings in `_schema.py` Literal annotations — they represent distinct TOML-level discriminators.

The `_GROUPING_DISPATCH` mapping type changed from `Mapping[str, str]` to `Mapping[str, RowSetGroupingKind]`. The if-chain comparisons in `_row_set_assembly.py` now compare against enum members directly.

Grep-post-condition: `grep -n "!= ['\"]withholding\|!= ['\"]foreign_asset" src/aeat/domain/calculations/registry/_bindings.py` returned 0 lines.

## Tests

Existing calculation and registry load tests passed.

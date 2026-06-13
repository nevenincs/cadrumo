---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'P01.S07'
related:
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
  - '[[2026-06-02-registry-hardening-m200-export-pressure-audit]]'
---

# P01.S07 Execution Record

## Step

`P01.S07`: Audit M200 export fragments near the reviewability ceiling;
`.vault/audit`.

## Result

Completed. The audit confirms M200 export pressure is now the top committed
TOML file-size pressure after the M100 completeness-manifest split sequence.

The next safe split target is:

- `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0028-modelo-200-page-019.part-002.toml`

That fragment has 1618 lines, one export layout, one record, and 117
`records.fields` entries. It can be split using existing record-field fragment
merge semantics; no loader or schema change is required.

## Artifacts

- `2026-06-02-registry-hardening-m200-export-pressure-audit`
- `2026-06-02-registry-hardening-next-work-p01-s07-review`

## Verification

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_committed_registry_toml_files_stay_reviewable src/aeat/domain/calculations/registry/test_registry_reviewability.py::test_registry_toml_fragments_stay_reviewable -q`
  - Result: 2 passed in 5.88s.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_directory_mode_merges_export_record_field_fragments_by_record_id -q`
  - Result: 1 passed in 0.29s.

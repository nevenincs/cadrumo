---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:5eb0ba631f11ac9797d233110a82f9714224877275531cde051d497bb42ab087'
step_id: 'S30'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Recover official cached positive integers from Total and Total: rows without extent inference, and model DP200000 as a typed variable envelope/composition wrapper outside fixed-width generation with a separately proven composition contract

## Scope

- `src/cadrumo/domain/calculations/registry/`
- `dev/registry/`

## Description

- Recover only cached positive integers following normalized `Total` or `Total:` labels.
- Require every workbook fixed-field sequence and variable-envelope prefix to start at offset 1 and remain exactly contiguous in source order; reject gaps and overlaps before terminal-total or composition validation.
- Preserve `DP200000` as one typed variable envelope with fixed prefix, variable body, relative closing suffix, and variable-total anchors.
- Carry typed variable-envelope state through semantic validation and `JoinedRecordDesign` without mapping it as a fixed record.
- Refuse fixed-width tree rendering unconditionally before target creation whenever a joined design contains any variable envelope; defer the separately typed composition proof and byte proof to `S34`.
- Reject duplicate, mixed, incomplete, discontinuous, or misordered envelope composition markers through the production workbook parser.
- Keep the provenance fixture on parser intermediate schema version 2 and prove version 1 is rejected as drift.

## Outcome

The source-derived total mapping remains nonempty and measures 76 fixed sheets. Representative anchors retain `DP200001!A119:C119 = 627` and `DP200DID!A49:C49 = 774`; every recovered total equals terminal parsed extent. `DP200000` remains total-free, retains prefix extent 328, body anchor `A14` at offset 329 with length `Variable`, closing anchor `A15` at relative offset `***` with length 18, and variable-total anchor `A16`.

The reopened review findings are remediated. Workbook fixed sheets and the variable prefix now require first offset 1 and exact contiguity. The semantic validator rejects duplicate envelope identities and fixed/envelope identity collisions. The join retains the exact parser-owned envelope tuple. Fixed-width rendering refuses before profile validation or output-directory creation. A focused real-source test parses the hash-pinned Modelo 200/2025 workbook, retains its real `DP200000` envelope through the production IR and semantic join, and proves rendering produces no output.

Focused parser, IR, semantic validation/join, provenance, and variable-envelope generation-gate verification passed with 51 tests and two upstream `openpyxl` warnings. The existing renderer compatibility suite passed with 18 tests without modifying its peer-owned test file. Scoped Ruff passed. Scoped BasedPyright passed with zero errors, warnings, or notes.

## Notes

The original implementation landed across commits `0316ec8f58`, `38d9447750`, `4aafa285c1`, and `e2b4ecf15a`; commit `727cff8e85` recorded the original split evidence, and `e3f6f68fcb` reopened the step after formal review. Shared-branch commit `4e00057887` swept the complete correction code and tests while the final gates were running: 8 added lines in `_export_tree.py`, 14 in `_semantic_map_join.py`, 21 in `_semantic_map_validation.py`, 7 added and 3 removed in `test_provenance_manifest.py`, 99 added in `test_variable_envelope_generation_gate.py`, 18 added and 1 removed in `_record_design.py`, and 163 added and 9 removed in `test_record_design.py`. Concurrent consolidation then landed the CLI-authored plan closure and execution-record updates across `b02b49cb58`, `671b6d8c82`, and newline-only `5cb080b6f0` before the prepared pathspec commit could run. Final HEAD contains the closed plan row and exact evidence; history was not rewritten or amended.

A trial extension of exact contiguity to all PDF parser output exposed six pre-existing PDF segmentation and sparse visual-chart behaviors outside the amended Modelo 200 workbook boundary. That trial was removed before final verification; no PDF behavior changed. No peer-owned provenance implementation or renderer test file was edited.

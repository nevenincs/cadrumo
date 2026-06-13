---
tags:
  - '#audit'
  - '#registry-workbook-parity-boundary'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---

# `registry-workbook-parity-boundary` audit: `workbook parity extraction boundary audit`

## Scope

Audited `src/aeat/domain/calculations/registry/_workbook_parity.py` as a
large registry production module that owns workbook discovery,
classification, conversion, runner execution, and registry-vs-workbook
parity comparison.

## Findings

### High

- `_workbook_parity.py` is 1,317 working-tree lines and combines DTOs,
  workbook scanning, formula-reference parsing, workbook-kind
  classification, coverage inventory, LibreOffice and Excel runner
  detection/execution, binary XLS conversion, registry-to-workbook parity
  comparison, backend verification, and failure-report construction.
- The file has no local diff at audit time, so it is a reasonable
  near-term implementation target after audit closure.
- `src/aeat/domain/calculations/registry/__init__.py` re-exports the
  public workbook-parity API. Extraction must preserve registry-root
  imports and should keep `_workbook_parity.py` as a compatibility facade
  during staged decomposition.

### Medium

- DTOs and enums are compact and shared by every family. They can either
  remain in the facade initially or move first to a small model module.
- Scanning and classification are a cohesive family:
  `discover_workbooks`, `scan_workbook`, `_scan_xlsx_contents`,
  `_scan_worksheet_cells`, `_classify_xlsx`, `_formula_references`, and
  related failure-report helpers.
- Runner/conversion is a cohesive family:
  `detect_workbook_runner`, `run_workbook_with_libreoffice`,
  `convert_binary_xls_with_libreoffice`,
  `converted_binary_xls_with_libreoffice`, Excel COM execution, and
  binary conversion context helpers.
- Parity comparison and backend verification are a cohesive family:
  `run_registry_workbook_parity`, `compare_registry_to_workbook`,
  `verify_workbook_backend`, `assert_workbook_scan_clean`, and
  `assert_formula_workbook_runner_ready`.
- `inventory_workbook_coverage` sits between scanning and reporting. It
  should move with scanning first unless implementation reveals tighter
  dependency on backend verification reports.

### Low

- The conversion helpers use external process and platform capabilities,
  so extraction should avoid changing timeout settings, error types, or
  executable-discovery behavior.

## Recommendations

1. Keep `_workbook_parity.py` as a compatibility facade during
   decomposition.
2. Extract shared DTOs/enums only if it simplifies imports; otherwise
   leave them in the facade until the first behavior family moves.
3. First safe extraction candidate: scanning/classification and coverage
   inventory. This avoids the highest-risk external runner code while
   reducing the largest pure-parser cluster.
4. Second extraction candidate: runner and binary conversion helpers.
   Preserve timeout settings, error classes, and process execution
   behavior exactly.
5. Third extraction candidate: parity comparison and backend verification
   orchestration.
6. Preserve public imports from `aeat.domain.calculations.registry`.
7. Each extraction commit should run `test_workbook_parity.py`,
   `test_public_api_boundaries.py`, workbook-kind/runner inventory tests,
   and any focused tests covering conversion or scan narrowing for the
   touched family.

## Codification candidates

- **Source:** finding High-1.
  **Rule slug:** `registry-workbook-parity-family-split`.
  **Rule:** Workbook parity decomposition must split scanning,
  runner/conversion, and comparison families behind compatibility
  re-exports while preserving external runner behavior.

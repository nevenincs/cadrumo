---
tags:
  - '#plan'
  - '#registry-workbook-compiler'
date: '2026-10-05'
tier: L1
related:
  - '[[2026-06-03-modelo-export-workbook-parity-adr]]'
  - '[[2026-06-03-modelo-export-visual-design-adr]]'
  - '[[2026-09-07-tuimodelo-form-projection-adr]]'
  - '[[2026-10-05-google-outbound-review-adr]]'
modified: '2026-10-06'
body_schema: body-v2
body_hash: 'sha256:0f580beccb13095cd0a687c99e81e43023510288d2bca329418ee40c9fc022ec'
---

# `registry-workbook-compiler` plan

## Description

Approved 2026-10-05

User approved the reusable registry-to-layout-to-workbook compiler after accepting the visual prototype. Preserve the prototype. Reuse SheetExportPlan and its formula translator; render declared pages, sections, fields, grids and repeating records without modelo-specific coordinates. Prove Modelo 130, 303 and a repeating-record revision. Generated layouts disclose review state, missing values remain unknown, and saved baselines never become scenario calculations. Workbook parity and visual-design ADRs govern shared typed facets and both transports, form-projection governs total placement, and outbound-review governs immutable baselines and separate scenarios. The user-approved prototype supplies the visual direction. Development fixture compilation does not claim production authority adoption.

The approved continuation covers every registry modelo and revision: ground templates in applicable official forms, preserve full calculation inputs and references using human-readable presentation, and prove populated native Sheets per template. Current inventory is 58 modelos and 160 revisions; generated placement coverage is not official-form fidelity or completed review. S04–S06 retain this full completion boundary.

## Steps

- [ ] `S01` - Extend shared presentation geometry and both materializers; `src/cadrumo/application/storage/calc_sheets/records.py, src/cadrumo/adapters/outbound/google, src/cadrumo/adapters/outbound/workbook`.
- [ ] `S02` - Compile declared pages, blocks and exact export-context fields into the shared workbook plan and read-only form projection; `src/cadrumo/application/storage/calc_sheets/form_workbook.py and tests, registry form schema and integrity, application form read models and TUI read-only context rendering, typed saved detail rows and revision identity and lossless application payload mirrors needed by declared repeating forms`.
- [ ] `S03` - Verify real registry generation and present generated demonstration workbooks; `dev and calc_sheets tests, separate Google Sheets demonstration files`.
- [ ] `S04` - Remove developer and machine metadata from all delivered form-template surfaces while preserving inputs and source references; `src/cadrumo/application/storage/calc_sheets, both workbook materializers and focused tests`.
- [ ] `S05` - Author and verify official-source-backed form designs for every registry modelo and revision; `dev/registry/form_layout, source corpus and registry form declarations, full-inventory acceptance tests`.
- [ ] `S06` - Generate and verify a populated native Google Sheet for every authored template; `dev/registry workbook generation and per-template live verification records`.

## Parallelization

Parent owns shared records, Google/XLSX adapters, integration, shared checks and commits. Once the shared facet contract is specified, renderer worker owns new form compiler modules and focused application tests, and verification worker owns development acceptance fixtures and real-registry tests. These assignments may run concurrently; workers preserve concurrent edits. Final review follows integration.

## Verification

Verify deterministic typed placement, complete casilla accounting, grids and repeating rows, missing values, malformed layouts, human labels and generated-layout disclosure. Compare both transports against the same geometry. Reuse formula translator and inspect form references to actual plan cells. Exercise real registry declarations for 130, 303 and a repeating model. Run focused pytest and configured format, lint, type and boundary checks, distinguishing unrelated failures. If available, publish separate generated demonstration Sheets and read back formulas and values; distinguish API verification from visual inspection.

For S04–S06, verify every revision individually against applicable official form pages and registry inputs. Record unplaced fields and missing context explicitly. Test generated workbook cells, notes, document properties, protections and support-sheet geometry for readable presentation while preserving all formula dependencies. Native populated Sheet generation and readback must be demonstrated per authored template; the three existing examples are regression cases, not full inventory acceptance. Distinguish official PDF visual inspection, local automated tests, native API readback and browser visual review.

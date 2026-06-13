---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-m353-standardization-plan]]'
---

# `schema-hardening-m353-standardization` Inventory

Modelo 353 is the largest remaining single-file modelo after the M322
standardization slice.

## Source Baseline

- Source file: `src/aeat/_data/registry/aeat/modelos/353.toml`
- Current line count: 569
- Revision count: 1
- Revision id: `2008-y-siguientes`
- Target layout: `modelos/353/manifest.toml` plus
  `modelos/353/revisions/2008-y-siguientes/revision.toml` and section
  fragments.

## Section Boundaries

- Lines 1-19: `[modelo]`
- Lines 20-34: `[revisions."2008-y-siguientes"]`
- Lines 35-44: `workbook_parity_refs` fragment 0001
- Lines 45-63: `verification_expectations` fragment 0001
- Lines 64-123: `bindings` fragment 0001
- Lines 124-227: `casillas` fragment 0001
- Lines 228-274: `formulas` fragment 0001
- Lines 275-298: `casillas` fragment 0002
- Lines 299-342: `live_cross_references` fragment 0001
- Lines 343-422: `application_links` fragment 0001
- Lines 423-430: `filing_schedules` fragment 0001
- Lines 431-470: `deadline_windows` fragment 0001
- Lines 471-541: `constructs` fragment 0001
- Lines 542-569: `completeness_manifest` fragment 0001

## Split Strategy

Preserve the registry content mechanically and keep all fragments scoped to the
single existing revision id. Repeated `casillas` groups remain separate ordered
fragments because the original file contains two non-contiguous casilla blocks.
No values, ids, labels, roles, formulas, filing schedules, deadline windows,
application links, constructs, completeness entries, or source citations should
be normalized during the move.

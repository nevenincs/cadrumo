---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-m390-standardization-plan]]'
---

# `schema-hardening-m390-standardization` Inventory

Modelo 390 is the largest remaining single-file modelo after the M720
standardization slice.

## Source Baseline

- Source file: `src/aeat/_data/registry/aeat/modelos/390.toml`
- Current line count: 808
- Revision count: 1
- Revision id: `2010-y-siguientes`
- Target layout: `modelos/390/manifest.toml` plus
  `modelos/390/revisions/2010-y-siguientes/revision.toml` and section
  fragments.

## Section Boundaries

- Lines 1-19: `[modelo]`
- Lines 20-34: `[revisions."2010-y-siguientes"]`
- Lines 35-44: `workbook_parity_refs` fragment 0001
- Lines 45-63: `verification_expectations` fragment 0001
- Lines 64-197: `bindings` fragment 0001
- Lines 198-379: `casillas` fragment 0001
- Lines 380-426: `formulas` fragment 0001
- Lines 427-450: `casillas` fragment 0002
- Lines 451-494: `live_cross_references` fragment 0001
- Lines 495-574: `application_links` fragment 0001
- Lines 575-582: `filing_schedules` fragment 0001
- Lines 583-652: `deadline_windows` fragment 0001
- Lines 653-673: `extraction_profiles` fragment 0001
- Lines 674-765: `constructs` fragment 0001
- Lines 766-808: `completeness_manifest` fragment 0001

## Split Strategy

Preserve the registry content mechanically and keep all fragments scoped to the
single existing revision id. Repeated `casillas` groups remain separate ordered
fragments because the original file contains two non-contiguous casilla blocks.
No values, ids, labels, roles, formulas, filing schedules, deadline windows,
application links, or source citations should be normalized during the move.

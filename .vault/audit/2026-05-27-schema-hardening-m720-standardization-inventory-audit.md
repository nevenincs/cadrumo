---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-m720-standardization-plan]]'
---

# `schema-hardening-m720-standardization` Inventory

Modelo 720 is the largest remaining single-file modelo after the M115
standardization slice.

## Source Baseline

- Source file: `src/aeat/_data/registry/aeat/modelos/720.toml`
- Current line count: 950
- Revision count: 1
- Revision id: `2013-y-siguientes`
- Target layout: `modelos/720/manifest.toml` plus
  `modelos/720/revisions/2013-y-siguientes/revision.toml` and section
  fragments.

## Section Boundaries

- Lines 1-24: `[modelo]`
- Lines 25-44: `[revisions."2013-y-siguientes"]`
- Lines 45-73: `casillas` fragment 0001
- Lines 74-89: `parameters` fragment 0001
- Lines 90-390: `bindings` fragment 0001
- Lines 391-413: `export_layouts` fragment 0001
- Lines 414-432: `workbook_parity_refs` fragment 0001
- Lines 433-453: `extraction_profiles` fragment 0001
- Lines 454-463: `verification_expectations` fragment 0001
- Lines 464-507: `live_cross_references` fragment 0001
- Lines 508-587: `application_links` fragment 0001
- Lines 588-595: `filing_schedules` fragment 0001
- Lines 596-753: `deadline_windows` fragment 0001
- Lines 754-825: `bindings` fragment 0002
- Lines 826-940: `constructs` fragment 0001
- Lines 941-950: `completeness_manifest` fragment 0001

## Split Strategy

Preserve the registry content mechanically and keep all fragments scoped to the
single existing revision id. Repeated `bindings` groups remain separate ordered
fragments because the original file contains two non-contiguous binding blocks.
No values, ids, labels, roles, export layout records, filing schedules,
deadline windows, application links, or source citations should be normalized
during the move.

---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-m115-standardization-plan]]'
---

# `schema-hardening-m115-standardization` Inventory

Modelo 115 is the largest remaining single-file modelo after the M190
standardization slice.

## Source Baseline

- Source file: `src/aeat/_data/registry/aeat/modelos/115.toml`
- Current line count: 989
- Revision count: 1
- Revision id: `2019-y-siguientes`
- Target layout: `modelos/115/manifest.toml` plus
  `modelos/115/revisions/2019-y-siguientes/revision.toml` and section
  fragments.

## Section Boundaries

- Lines 1-16: `[modelo]`
- Lines 17-28: `[revisions."2019-y-siguientes"]`
- Lines 29-47: `parameters` fragment 0001
- Lines 48-117: `casillas` fragment 0001
- Lines 118-141: `formulas` fragment 0001
- Lines 142-666: `export_layouts` fragment 0001
- Lines 667-705: `extraction_profiles` fragment 0001
- Lines 706-740: `live_cross_references` fragment 0001
- Lines 741-750: `workbook_parity_refs` fragment 0001
- Lines 751-761: `verification_expectations` fragment 0001
- Lines 762-795: `constructs` fragment 0001
- Lines 796-891: `application_links` fragment 0001
- Lines 892-973: `deadline_windows` fragment 0001
- Lines 974-989: `completeness_manifest` fragment 0001

## Split Strategy

Preserve the registry content mechanically and keep all fragments scoped to the
single existing revision id. The export-layout block is the largest contiguous
section and will remain one bounded fragment for this slice. No values, ids,
labels, roles, formulas, export offsets, application links, deadline windows,
or source citations should be normalized during the move.

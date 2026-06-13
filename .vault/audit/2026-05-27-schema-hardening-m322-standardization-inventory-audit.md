---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-m322-standardization-plan]]'
---

# `schema-hardening-m322-standardization` Inventory

Modelo 322 is the largest remaining single-file modelo after the M390
standardization slice.

## Source Baseline

- Source file: `src/aeat/_data/registry/aeat/modelos/322.toml`
- Current line count: 573
- Revision count: 1
- Revision id: `2008-y-siguientes`
- Target layout: `modelos/322/manifest.toml` plus
  `modelos/322/revisions/2008-y-siguientes/revision.toml` and section
  fragments.

## Section Boundaries

- Lines 1-19: `[modelo]`
- Lines 20-34: `[revisions."2008-y-siguientes"]`
- Lines 35-44: `workbook_parity_refs` fragment 0001
- Lines 45-66: `verification_expectations` fragment 0001
- Lines 67-126: `bindings` fragment 0001
- Lines 127-230: `casillas` fragment 0001
- Lines 231-277: `formulas` fragment 0001
- Lines 278-301: `casillas` fragment 0002
- Lines 302-345: `live_cross_references` fragment 0001
- Lines 346-425: `application_links` fragment 0001
- Lines 426-434: `filing_schedules` fragment 0001
- Lines 435-474: `deadline_windows` fragment 0001
- Lines 475-545: `constructs` fragment 0001
- Lines 546-573: `completeness_manifest` fragment 0001

## Split Strategy

Preserve the registry content mechanically and keep all fragments scoped to the
single existing revision id. Repeated `casillas` groups remain separate ordered
fragments because the original file contains two non-contiguous casilla blocks.
No values, ids, labels, roles, formulas, filing schedules, deadline windows,
application links, constructs, completeness entries, or source citations should
be normalized during the move.

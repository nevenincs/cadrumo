---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-m184-standardization-plan]]'
---

# `schema-hardening-m184-standardization` Inventory

Modelo 184 is the largest remaining single-file modelo after the M353
standardization slice.

## Source Baseline

- Source file: `src/aeat/_data/registry/aeat/modelos/184.toml`
- Current line count: 483
- Revision count: 1
- Revision id: `2015-y-siguientes`
- Target layout: `modelos/184/manifest.toml` plus
  `modelos/184/revisions/2015-y-siguientes/revision.toml` and section
  fragments.

## Section Boundaries

- Lines 1-22: `[modelo]`
- Lines 23-40: `[revisions."2015-y-siguientes"]`
- Lines 41-116: `casillas` fragment 0001
- Lines 117-132: `workbook_parity_refs` fragment 0001
- Lines 133-149: `extraction_profiles` fragment 0001
- Lines 150-166: `verification_expectations` fragment 0001
- Lines 167-210: `live_cross_references` fragment 0001
- Lines 211-250: `application_links` fragment 0001
- Lines 251-258: `filing_schedules` fragment 0001
- Lines 259-353: `deadline_windows` fragment 0001
- Lines 354-401: `bindings` fragment 0001
- Lines 402-461: `constructs` fragment 0001
- Lines 462-483: `completeness_manifest` fragment 0001

## Split Strategy

Preserve the registry content mechanically and keep all fragments scoped to the
single existing revision id. Modelo 184 contains one contiguous casilla group
and later row-producer bindings; these stay in source order as ordered
fragments. No values, ids, labels, roles, extraction profiles, bindings,
filing schedules, deadline windows, constructs, completeness entries, or
source citations should be normalized during the move.

---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-m190-standardization-plan]]'
---

# `schema-hardening-m190-standardization` Inventory

Modelo 190 is the largest remaining single-file modelo after the M130
standardization slice.

## Source Baseline

- Source file: `src/aeat/_data/registry/aeat/modelos/190.toml`
- Current line count: 1,023
- Revision count: 1
- Revision id: `2024-y-siguientes`
- Target layout: `modelos/190/manifest.toml` plus
  `modelos/190/revisions/2024-y-siguientes/revision.toml` and section
  fragments.

## Section Boundaries

- Lines 1-26: `[modelo]`
- Lines 27-49: `[revisions."2024-y-siguientes"]`
- Lines 50-277: `bindings` fragment 0001
- Lines 278-562: `relations` fragment 0001
- Lines 563-606: `casillas` fragment 0001
- Lines 607-664: `formulas` fragment 0001
- Lines 665-682: `extraction_profiles` fragment 0001
- Lines 683-705: `live_cross_references` fragment 0001
- Lines 706-715: `workbook_parity_refs` fragment 0001
- Lines 716-725: `verification_expectations` fragment 0001
- Lines 726-805: `application_links` fragment 0001
- Lines 806-901: `bindings` fragment 0002
- Lines 902-975: `constructs` fragment 0001
- Lines 976-1010: `dependency_classifications` fragment 0001
- Lines 1011-1023: `completeness_manifest` fragment 0001

## Split Strategy

Preserve the registry content mechanically and keep all fragments scoped to the
single existing revision id. Repeated `bindings` groups remain separate ordered
fragments because the original file contains two non-contiguous binding blocks.
No values, ids, labels, roles, formulas, relations, application links, or source
citations should be normalized during the move.

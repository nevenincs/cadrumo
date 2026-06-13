---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-m193-standardization-plan]]'
---

# `schema-hardening-m193-standardization` Inventory

Modelo 193 is the largest remaining single-file modelo after the M184
standardization slice.

## Source Baseline

- Source file: `src/aeat/_data/registry/aeat/modelos/193.toml`
- Current line count: 478
- Revision count: 1
- Revision id: `2024-y-siguientes`
- Target layout: `modelos/193/manifest.toml` plus
  `modelos/193/revisions/2024-y-siguientes/revision.toml` and section
  fragments.

## Section Boundaries

- Lines 1-24: `[modelo]`
- Lines 25-45: `[revisions."2024-y-siguientes"]`
- Lines 46-81: `bindings` fragment 0001 for Modelo 123 annual-summary inputs
- Lines 82-126: `relations` fragment 0001
- Lines 127-167: `casillas` fragment 0001
- Lines 168-203: `formulas` fragment 0001
- Lines 204-235: `extraction_profiles` fragment 0001, including adjacent grounding comments
- Lines 236-258: `live_cross_references` fragment 0001
- Lines 259-268: `workbook_parity_refs` fragment 0001
- Lines 269-278: `verification_expectations` fragment 0001
- Lines 279-350: `application_links` fragment 0001
- Lines 351-415: `bindings` fragment 0002 for per-perceptor row producers
- Lines 416-450: `constructs` fragment 0001
- Lines 451-465: `dependency_classifications` fragment 0001
- Lines 466-478: `completeness_manifest` fragment 0001

## Split Strategy

Preserve the registry content mechanically and keep all fragments scoped to the
single existing revision id. Modelo 193 contains two non-contiguous binding
groups: annual-summary inputs from Modelo 123 and per-perceptor row producers.
Those groups remain separate ordered fragments. No values, ids, labels, roles,
relations, formulas, extraction profiles, bindings, constructs, dependency
classifications, completeness entries, or source citations should be normalized
during the move.

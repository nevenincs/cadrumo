---
tags:
  - '#audit'
  - '#registry-reviewability-pressure'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-registry-reviewability-pressure-plan]]'
---

# `registry-reviewability-pressure` audit: `split decision`

## Purpose

Decide which inline-only revision directories should be mechanically split in
this plan, based on the S01 pressure inventory and read-only layout inspection.

## Decision

Split M123 now.

Defer M369.

Do not tighten row-width gates until the separate M100 row-width pressure has
been mechanically reformatted or explicitly deferred.

## Rationale

M123 has the strongest reviewability pressure signal:

- `123/revisions/2024-y-siguientes/revision.toml` is 1,218 lines, only 32 lines
  below the 1,250-line baseline gate.
- `123/revisions/2019-2023/revision.toml` is 932 lines, large enough that
  section-level review would be materially clearer.
- Both revision directories already use the accepted fragment-directory layout
  and already keep `completeness-manifest.toml` outside `revision.toml`.
- The remaining inline fields are ordinary repeatable revision fields supported
  by the generic fragment compiler: `casillas`, `formulas`, `export_layouts`,
  `extraction_profiles`, `live_cross_references`, `workbook_parity_refs`,
  `verification_expectations`, `constructs`, `application_links`, and
  `deadline_windows`.

M369 is lower priority:

- Its largest revision file is `369/revisions/esquema-union/revision.toml` at
  469 lines.
- It has no row-width pressure.
- A split would improve consistency but would not address a near-threshold
  artifact. Deferring it avoids unnecessary churn in a legally sensitive
  registry without losing current reviewability safety.

M100 row-width pressure is real but independent:

- `100/revisions/2025/casillas/0618-0552.toml` has a 572-character row, only
  three characters below the 575-character baseline.
- The file is already a small casilla fragment, so revision fragmentation does
  not solve the issue. Any repair should be a separate value-preserving TOML
  formatting slice.

## Authorised S03 scope

S03 may mechanically split M123 only. The split must preserve loaded
`ModeloDefinition` equality before and after the move, retain the scalar
revision metadata in `revision.toml`, and move repeatable sections into
field-group fragments under each revision directory.

S04 should be closed as a tracked deferral unless new evidence appears before
that step starts.

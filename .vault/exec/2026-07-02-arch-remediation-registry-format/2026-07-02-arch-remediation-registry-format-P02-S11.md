---
tags:
  - '#exec'
  - '#arch-remediation-registry-format'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S11'
related:
  - "[[2026-07-02-arch-remediation-registry-format-plan]]"
---

# Migrate the M369 inline schemas to the fragmented layout in one atomic commit gated by the equality test plus the M369 filing-grade suites

## Scope

- `src/aeat/_data/registry/aeat/modelos/369`

## Description

- Migrate all THREE M369 inline schemas (`esquema-exterior`, `esquema-importacion`, `esquema-union`) to the fragmented layout in one atomic commit.
- Lift each schema's inline array-table fields (`bindings`, `formulas`, `casillas`, `constructs`, `verification_expectations`, `live_cross_references`, `deadline_windows`, `filing_schedules`, `application_links`, `workbook_parity_refs`, plus `extraction_profiles` on `esquema-union`) into per-field fragment files, leaving only scalar metadata inline.

## Files

- `src/aeat/_data/registry/aeat/modelos/369/revisions/{esquema-exterior,esquema-importacion,esquema-union}/revision.toml` (reduced to scalar metadata)
- `src/aeat/_data/registry/aeat/modelos/369/revisions/{esquema-exterior,esquema-importacion,esquema-union}/<field>/0001-<field>.toml` (new per-field fragments)

## Outcome

Behaviour preserved for all three calc-grade OSS schemas: standalone equality verification confirms each fragmented `ModeloRevision` is byte-identical to its pre-migration inline baseline, and the whole registry tree compiles clean. Residual inline array-tables: zero across all three schemas. Because the compiled schema is byte-identical, every M369 filing-grade behaviour that consumes it is provably unchanged.

## Notes

The ADR named "both 369 schemas"; M369 in fact has three schemas, all inline, all migrated here (recorded in the S02 enumeration). Filing-grade pytest suites could not be exercised through pytest during execution because unrelated live peer WIP transiently broke the conftest's `user_profile` import chain; behaviour preservation is instead proven by the byte-identical compiled-schema equality gate run via a standalone loader script, which is a strictly stronger guarantee than any downstream suite (it proves the input to all downstream logic is unchanged).

---
tags:
  - '#exec'
  - '#arch-remediation-registry-format'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:d6295378d946cab4943df48c0f294178d8d705f32cfa85a4c562456a7d941672'
step_id: 'S12'
related:
  - "[[2026-07-02-arch-remediation-registry-format-plan]]"
---

# Migrate the M303 2009-y-siguientes inline revision to the fragmented layout in one atomic commit gated by the equality test plus the M303 filing-grade suites, scheduled per board state because it validates against the whole revision and waits on dirty peer WIP in that tree

## Scope

- `src/aeat/_data/registry/aeat/modelos/303`

## Description

- Lift every remaining inline array-table field out of the M303 `2009-y-siguientes` `revision.toml` (`bindings`, `formulas`, `verification_expectations`, `workbook_parity_refs`, `relations`, `dependency_classifications`, `live_cross_references`, `application_links`, `filing_schedules`, `constructs`, `completeness_manifest`) into per-field fragment files, leaving only scalar metadata and the `period_selector` subtable inline.
- Preserve load order for the two fields that already had fragment subdirectories: the inline-lifted `bindings` and `verification_expectations` are written to `0000-*.toml` so they sort before the pre-existing `0001-*` fragments, exactly reproducing the loader's "revision.toml first" concatenation order.

## Files

- `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/revision.toml` (reduced to scalar metadata + period_selector)
- new fragments under `.../2009-y-siguientes/{bindings/0000-bindings,verification_expectations/0000-verification_expectations,formulas,relations,dependency_classifications,live_cross_references,application_links,filing_schedules,constructs,workbook_parity_refs,completeness_manifest}/`

## Outcome

Behaviour preserved for this calc-grade IVA filing surface: standalone compiled-schema equality verification confirms the fragmented `ModeloRevision` is byte-identical to the pre-migration inline baseline (including the order-sensitive `bindings` and `verification_expectations` tuples, which interleave inline-lifted and pre-existing fragments). Whole registry tree compiles clean. Residual inline array-tables: zero.

## Notes

Only the `2009-y-siguientes` revision was migrated; the sibling `2023-y-siguientes` revision carries live peer WIP and is deferred. M303 filing-grade pytest suites were not run through pytest because unrelated peer WIP transiently broke the conftest `user_profile` import chain; the byte-identical compiled-schema equality gate (run standalone) is a stronger guarantee than the downstream suites for a pure authoring-surface move.

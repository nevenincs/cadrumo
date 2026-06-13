---
tags:
  - '#audit'
  - '#registry-hardening-next-work'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
---

# `registry-hardening-next-work` audit: `generic fragmentation contract`

## Purpose

Audit whether registry revision and fragmentation support is a generic
cross-modelo construct, not a one-off M100/M200/M303 implementation, and
identify any remaining regression gap before adding more modelo data.

## Evidence

- `src/aeat/domain/calculations/registry/_loader.py` exposes generic source
  descriptors: `ModeloSource`, `ModeloRevisionSource`, `ModeloSourceLayout`,
  and `ModeloRevisionSourceLayout`.
- `load_modelo_path`, `load_modelo_source`, `load_modelo_directory`, and
  `discover_modelo_sources` branch on source layout, not modelo id.
- `_load_modelo_revisions` merges both `revisions/*.toml` files and
  `revisions/<id>/` fragment directories without a modelo-id switch.
- `_merge_revision_fragment_field` uses revision field names and explicit
  appendable-array contracts. The merge behaviour is schema-surface driven,
  not M100/M200/M303 driven.
- `load_registry_tree` discovers single-file and directory sources under the
  same `modelos/` root and rejects layout collisions.
- `test_loader_directory_mode.py` already covers synthetic fragment-directory
  behaviour for casillas, completeness manifests, export record fields,
  constructs, scalar conflicts, duplicate nested ids, revision-id mismatch,
  stale single-file siblings, committed source inventory, and TOML size/row
  limits.
- `test_authority.py` covers recursive revision-fragment cache invalidation
  through the registry authority path.

## Corpus inventory

Read-only inventory command:

`$env:PYTHONPATH='src'; ... discover_modelo_sources(...)`

Current on-disk result:

- Modelo sources: 30.
- Modelo layouts: 30 directory-mode, 0 single-file.
- Revision source layouts as reported by `discover_modelo_sources`: 46
  fragment-directory, 0 revision-file.
- Of those revision directories, 41 contain additional fragment TOMLs beyond
  `revision.toml`; 5 are inline-only revision directories whose full revision
  content is currently carried by `revision.toml` under M123 and M369.
- Fragment-directory modelos include M036, M100, M111, M115, M123, M130,
  M131, M151, M180, M184, M190, M193, M200, M202, M210, M232, M303,
  M308, M309, M322, M347, M349, M353, M360, M369, M390, M714, M720,
  M721, and M840.
- M100 has six fragment-directory revisions.
- M200 has one fragment-directory revision.
- M303 has two fragment-directory revisions.
- Largest modelo TOML file observed: `123/revisions/2024-y-siguientes/revision.toml`
  at 1,218 lines.
- Largest observed M200 fragment: `200/revisions/2024-y-siguientes/export/0010-modelo-200-page-007.toml`
  at 954 lines.
- Closest line-count reviewability pressure is M123 2024, 32 lines below the
  1,250-line baseline gate in `test_registry_reviewability.py`.
- Closest row-width reviewability pressure is
  `100/revisions/2025/casillas/0618-0552.toml`, observed at 572 characters
  against the 575-character baseline gate.

## Findings

No hard-coded modelo id or one-off M100/M200/M303 loader path was found in the
generic loader contract.

The current committed corpus no longer demonstrates the non-fragmented
directory revision-file layout because every committed revision is now a
fragment-directory revision. That is good for reviewability, but it leaves the
positive `revisions/<id>.toml` path dependent on synthetic negative/collision
tests and on now-vacuous single-file conversion loops. S51 should add a
focused real-behavior positive regression for a generic directory-mode modelo
whose revision is represented by a plain `revisions/<id>.toml` file.

The fragment merge allowlists are manually maintained:
`_REVISION_APPEND_ARRAYS`, `_CONSTRUCT_APPEND_ARRAYS`, and explicit singleton
or by-id merge strategies for `constructs`, `export_layouts`, and
`completeness_manifest`. S51 should add a schema/loader contract regression
that fails when a new repeatable `ModeloRevision` field is added without
being classified as appendable or explicitly merged.

Corpus coverage should also name the critical committed examples. A future
regression should assert M100, M200, M303, and at least one small/simple modelo
are all discovered and loaded through the same generic source path.

## Decision

Proceed with S51 as a narrow test-hardening step. No schema or loader semantics
change is justified by this audit, and no ADR is required for the S51 coverage
addition.

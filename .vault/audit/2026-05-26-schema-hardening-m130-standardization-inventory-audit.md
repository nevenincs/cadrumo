---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-26-schema-hardening-m130-standardization-plan]]'
  - '[[2026-05-26-schema-hardening-m131-fragmentation-review-audit]]'
---

# M130 Standardization Inventory

Modelo 130 is the largest remaining single-file modelo after the M131
fragmentation pass. It is below the active TOML line cap, but standardizing it
onto the directory/fragments substrate reduces layout variance across the
registry and proves the generic fragment support also works for single-revision
modelos.

## Source Baseline

| Source | Lines | Layout |
| --- | ---: | --- |
| `modelos/130.toml` | 1,653 | single file |

## Section Boundaries

| Lines | Section |
| ---: | --- |
| 1-11 | manifest |
| 12-18 | revision |
| 19-53 | parameters |
| 54-340 | casillas |
| 341-352 | bindings |
| 353-494 | formulas |
| 495-506 | bindings |
| 507-546 | formulas |
| 547-1267 | export_layouts |
| 1268-1301 | extraction_profiles |
| 1302-1344 | live_cross_references |
| 1345-1354 | workbook_parity_refs |
| 1355-1369 | verification_expectations |
| 1370-1411 | constructs |
| 1412-1507 | application_links |
| 1508-1589 | deadline_windows |
| 1590-1653 | completeness_manifest |

## Split Strategy

Create `modelos/130/manifest.toml` from the `[modelo]` block and
`modelos/130/revisions/2019-y-siguientes/revision.toml` from the scalar
revision table. Move every contiguous revision section run into a numbered
fragment under a section directory. Repeated binding and formula runs remain
separate numbered fragments to preserve source order and avoid semantic merging.

## Edge Tracking

EDGE-2026-05-26-007 | NEXT | M130 is a single-revision standardization target,
not an emergency file-size mitigation. The split should prove the fragment
substrate can be used uniformly for single-revision modelos without requiring
per-modelo loader rules.

EDGE-2026-05-26-008 | WATCH | Remaining single-file modelos after M130 should
be selected by policy and churn tolerance, not only by file size. M190, M115,
M720, and M390 are the next largest single-file candidates.

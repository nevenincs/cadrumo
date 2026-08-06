---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:9216091123d97a6df4f3b52920d97dd9a5414baa82192cbe472a74e03e9218fb'
step_id: 'S48'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# Test missing source backed bindings cannot silently calculate zero

## Scope

- `src/aeat/application/modelo/test_source_mesh_missing_sources.py`

## Description

- Add `test_source_mesh_missing_sources.py` under `application/modelo/tests/`.
- Assert every source kind the committed registry declares (from S44's `source_inventory()`) resolves `ENROLLED` or `DEFERRED` under the LIVE enrolled set `BUCKET_AGGREGATION_OWNED_SOURCES` via `build_binding_source_dispositions` — a declared kind owned by no live resolver and not deferred would classify `RESERVED` and fail.
- Assert `ACCEPTED_BUCKET_AGGREGATION_SOURCE_KINDS` (the set the live novel-source gate enforces) covers every declared kind, so no declared source is rejected-or-blanked as novel.
- Assert a synthetic novel source raises `ModeloAggregationBindingError` via `assert_no_novel_source_kinds` rather than compiling into a silently-zero revision.
- Add anti-tautology: the accepted set excludes every `RESERVED` kind (so the coverage assertion is non-vacuous), and a non-empty declared set floor.

## Outcome

- New test file; 5 tests green. This is the live-mesh half of the connectivity gate: it ties the committed registry inventory to the actual enrolled resolvers and proves a missing/unrouted source cannot silently calculate zero.
- Uses intra-package `_calculation_source_policy` (the live enrolled/accepted sets) and the domain `source_inventory()` (application-to-domain import is allowed), avoiding the peer-WIP `application/modelo/__init__.py` facade.
- Gates green: ruff + ty clean; collect-only clean; runs alongside `test_source_boundary_and_enrollment.py`, `test_binding_source_kind_mesh_parity.py`, `test_source_kind_enrollment_status.py` (37 tests total in the enrollment cluster, all pass).

## Notes

- The novel-source `model_construct` injection mirrors the existing `test_source_boundary_and_enrollment.py` pattern; this file's focus is the missing/novel-source silent-zero contract specifically, keeping the S48 deliverable self-contained.

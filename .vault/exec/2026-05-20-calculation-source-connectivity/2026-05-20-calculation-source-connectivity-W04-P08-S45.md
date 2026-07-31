---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:5cc3994b6983fcd460a4fd93890ae757060cf026fdaeb4a27a30920acfe7b4f1'
step_id: 'S45'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# Validate every source backed binding is resolved manual or explicitly blocked

## Scope

- `src/aeat/application/aggregation/_source_mesh.py`

## Description

- Verify-and-close: the "every source-backed binding is resolved, manual, or explicitly blocked" validation is already realized in `_source_mesh.py` at HEAD.
- Confirm `build_binding_source_dispositions` partitions every `BindingSourceKind` into exactly one of `ENROLLED`, `DEFERRED`, or `RESERVED`, raising `AggregationValidationError` if a member is unaccounted or double-counted.
- Confirm `DEFERRED_SOURCE_KINDS` (derived from `DEFERRED_SOURCE_KIND_TARGETS`) and `RESERVED_SOURCE_KINDS` supply the non-enrolled partitions, and `collect_unhandled_source_diagnostics` emits a standing advisory for a declared source with no enrolled resolver rather than a silent blank.

## Outcome

- Requirement satisfied at HEAD; no code change needed. Resolved = enrolled resolver; manual = `manual_input`; explicitly blocked = deferred advisory (or reserved headroom the S47 gate refuses in committed revisions).
- Gate evidence green: `test_binding_source_kind_mesh_parity.py` (disposition registry covers every enum member; enrolled partition equals the owned mesh set; deferred partition equals `DEFERRED_SOURCE_KINDS`), `test_source_kind_enrollment_status.py` (every deferred kind carries a resolvable owning decision record + trigger), and `test_source_boundary_and_enrollment.py`.

## Notes

- The novel-source boundary gate `assert_no_novel_source_kinds` (the enforcement companion to this validation) lives in `_calculation_actions.py`, consuming `ACCEPTED_BUCKET_AGGREGATION_SOURCE_KINDS` from `_calculation_source_policy` (the application projection of the `_source_mesh.py` disposition registry).

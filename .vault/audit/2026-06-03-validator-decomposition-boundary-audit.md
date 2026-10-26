---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-06-03'
modified: '2026-10-03'
body_hash: 'sha256:ee968de22efc0a67d790cecb09d87192cc7e1c119e0e97304c9c332f7a7f3d46'
related: []
---

# Validator Decomposition Boundary Audit

## Scope

Audit the current registry validation modules before extracting additional validator components.

## Findings

- `_validate.py` is 210 lines and is already an orchestration module, not the original monolith.
- The largest validation module is `_validate_cross_revision.py` at 409 lines; it mixes hard-fail overlap drift, strict continuity evolution validation, retired continuity checks, advisory summaries, and formatting.
- `_validate_revision_sections.py` is 254 lines and is a broad per-revision dispatcher. It should remain a coordinator unless a later audit proves one section group has enough complexity to extract.
- `_validate_references.py` is 233 lines and already separates snapshot referential integrity from registry-level validation. Its remaining pressure is per-section reference loops, not public API shape.
- Public imports should remain stable: `RegistryValidator` is re-exported from `registry.__init__`, and cross-revision helpers are also re-exported there. W02 extraction should not change this public surface.

## Recommended Extraction Order

1. Split `_validate_cross_revision.py` into policy-focused helpers first:
   - overlap drift hard-fail policy;
   - strict continuity evolution checks;
   - advisory non-overlap summaries;
   - formatting helpers.
2. Keep `_validate.py` as the public validator orchestrator until the cross-revision module is under the local size band.
3. Treat `_validate_revision_sections.py` as a second-order target after cross-revision extraction, because it already delegates to section modules and does not contain the densest policy logic.

## Verification

- The historical check

## Notes

The W02 plan title still names validation module decomposition, but the actual first implementation step should target `_validate_cross_revision.py`, not `_validate.py`.

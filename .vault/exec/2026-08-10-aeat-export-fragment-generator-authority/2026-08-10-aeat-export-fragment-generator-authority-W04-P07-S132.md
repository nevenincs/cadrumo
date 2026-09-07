---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:96bf8d1a8dc79b5388f8deffc250009451c5fdb7ff1b798fb410aacf6e220a0c'
step_id: 'S132'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# Replace the hand-maintained generated-tree enrolment table with a deterministic projection of every provenance-attested export tree in the validated registry, derive each check coordinate through canonical law-selection coordinates, prove every published generated tree is included automatically and every filing revision without generated provenance remains explicitly accounted for by the canonical filing-export residue authority, and remove stale claims that explicit manual enrolment is authoritative without loosening any generator matcher or adding casts.

## Scope

- `dev/registry/tests/test_generated_export_trees.py`
- `dev/registry/tests/test_declaration_invariant_gates.py`
- `dev/registry/tests/test_m303_generated_envelope_proof.py`

## Changes

- `M` `dev/registry/tests/test_generated_export_trees.py`
- `M` `dev/registry/tests/test_declaration_invariant_gates.py`
- `M` `dev/registry/tests/test_m303_generated_envelope_proof.py`
- `verify:` `uv run basedpyright dev/registry/tests/test_generated_export_trees.py dev/registry/tests/test_declaration_invariant_gates.py dev/registry/tests/test_m303_generated_envelope_proof.py` -> `pass`
- `verify:` `uv run ruff check dev/registry/tests/test_generated_export_trees.py dev/registry/tests/test_declaration_invariant_gates.py dev/registry/tests/test_m303_generated_envelope_proof.py` -> `pass`
- `verify:` focused enrollment and Modelo 390 isolation tests -> `2 passed`
- `verify:` direct canonical filing-export residue projection -> `69 filing revisions accounted for with non-empty owner, reconsideration condition, and detail`

## Notes

The complete generated-tree module reached all dynamically projected rows but inherited 27 current reproduction failures: all 27 differ in generated provenance and both Modelo 347 revisions additionally carry the already-ledgered record drift. This is a live input-versus-published-artifact condition, not a filtered enrollment or type-check failure. The separate canonical two-channel integration test is currently blocked by unrelated concurrent `snapshot_ref` contract work and fails while constructing its pre-existing Modelo 200 vector before exercising this Step.

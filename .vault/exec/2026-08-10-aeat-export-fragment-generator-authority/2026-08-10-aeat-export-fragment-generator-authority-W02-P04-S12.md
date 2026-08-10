---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:cd01bcc4bfbc135e39aa7fad497b0649201b39da8f53ccf13653c3d23f32b560'
step_id: 'S12'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# Implement check mode that independently regenerates and rejects semantic, provenance, or byte drift

## Scope

- `dev/registry/`

## Description

- Add `GeneratedExportTreeCheckContext` and `check_generated_export_tree` as the read-only regeneration boundary.
- Render only into an absent candidate `export/` directory beneath an explicit isolated temporary root, then validate it through S10.
- Require the published target to attest current source, semantic-map, schema, derivation, file, and normalized loader authority before exact member-and-byte comparison.
- Reject obsolete sibling and direct registry surfaces and every linked path component before candidate rendering or target reads.
- Add real filesystem and loader proofs for success, authority drift, byte drift, manifest/schema drift, missing and extra members, obsolete surfaces, candidate reuse, and redirected symlink refusal.

## Outcome

The checker independently regenerates a candidate and refuses every target divergence without publishing, repairing, or writing to the published target. The independent review identified a candidate ancestor-link escape before S10; the component-wise link gate and real symlink proof resolved it, and re-review passed with no remaining critical, high, or medium finding.

Focused S12 proof passed 14 tests. The full `dev/registry/tests` suite passed 105 tests. Owned Ruff, formatting, and BasedPyright checks were clean.

## Notes

The first `vault add exec` invocation exceeded its command-response limit but created the scaffold successfully; no target registry content was changed. Whole-directory Ruff and type runs still report unrelated peer diagnostics outside the S12 files.

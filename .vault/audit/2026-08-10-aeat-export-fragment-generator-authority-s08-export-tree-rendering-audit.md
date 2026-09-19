---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:7a6cd872e286742296fdea1e5640e146d8fc1925244f255385ad42e325c31538'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# `aeat-export-fragment-generator-authority` audit: `s08 export tree rendering`

## Scope

Independent review of S08's deterministic complete export-tree renderer, its source-hash-pinned profile boundary, canonical TOML partitioning, fail-closed normalization, and real filesystem and loader proofs.

## Findings

### s08 export tree rendering | high | Missing declared record totals were initially accepted

The renderer initially accepted an IR record without `declared_total`, which could permit a generated output with an inferred terminal extent. It now refuses a missing total before rendering and a real render test proves the destination remains empty.

### s08 export tree rendering | high | Geometry initially checked only terminal extent

The initial implementation did not prove exact contiguous field geometry. It now requires the first field at offset one, every subsequent field immediately after the prior field, and the terminal end equal to the declared total. Real render tests cover bad first offset, gap, overlap, and terminal mismatch, each refusing without output.

### s08 export tree rendering | pass | Re-review accepted the corrected renderer

The independent re-review confirmed both high findings are resolved. The full `dev/registry` suite, scoped formatting, linting, and strict typing completed successfully in the corrected state.

## Recommendations

- Preserve the exact geometry proof at the renderer boundary; later registry validation is additional defense and must not become its replacement.
- Add a source-hash-pinned normalization adjudication before admitting any currently unsupported official type or content form.

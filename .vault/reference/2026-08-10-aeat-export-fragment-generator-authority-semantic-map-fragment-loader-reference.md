---
tags:
  - '#reference'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:431e37b6a4854115f1284aad25d2878b6fa1e93a8f7999b8f1143e20a317d8aa'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
---

# `aeat-export-fragment-generator-authority` reference: `semantic-map fragment loader`

The persisted semantic-map boundary needs a small development-only compiler, not a second semantic schema. This reference compares the local strict-fragment implementations that govern S42 and records the chosen reusable contract.

## Summary

It treats a real non-linked directory containing only direct TOML children as one authored authority, sorts filenames before parsing, hydrates strict frozen fragment models, refuses duplicate fragment identifiers and design-identity drift, and compiles into one aggregate. Its real-filesystem tests exercise enumeration-order independence, malformed siblings, duplicate identifiers, and conflicting authority.

A semantic-map loader should reuse `read_toml` and `freeze_toml`; importing `rtoml` or translating arrays independently would redeclare that boundary.

The narrow S42 format is `schema_version`, `fragment_id`, `modelo`, `design_epoch`, plus the existing `SemanticMapRecord` and `SemanticMapEntry` arrays. Filenames use `NNNN-<fragment_id>.toml`, and the suffix must equal the authored identifier. Compilation refuses empty fragments or aggregates, non-TOML and linked members, malformed or unknown fields, duplicate fragment identifiers, cross-fragment design drift, exact record-anchor collisions, export-record-id collisions, exact field-anchor collisions, and export-field-id collisions. Records and entries are canonicalized by their exact semantic keys before constructing the existing `SemanticMap`.

The loader must not read parser intermediates, snapshots, render profiles, generated layouts, neighbouring mappings, or legacy export trees.

The public development facade exports the existing semantic-map types and one `load_semantic_map` entry point. Real tests must create actual TOML fragments and prove canonical order, strict hydration, every collision class, filename-to-id agreement, and absence of a fallback surface.

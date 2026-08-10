---
tags:
  - '#reference'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:2c0e47f62c7b5548ea4297655965883dcf87cc02c9a03029a907229b3b7b95b7'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
---
# `aeat-export-fragment-generator-authority` reference: `semantic-map fragment loader`

The persisted semantic-map boundary needs a small development-only compiler, not a second semantic schema. This reference compares the local strict-fragment implementations that govern S42 and records the chosen reusable contract.

## Summary

`dev/registry/_render_profile.py` is the nearest architectural analogue. It treats a real non-linked directory containing only direct TOML children as one authored authority, sorts filenames before parsing, hydrates strict frozen fragment models, refuses duplicate fragment identifiers and design-identity drift, and compiles into one aggregate. Its real-filesystem tests exercise enumeration-order independence, malformed siblings, duplicate identifiers, and conflicting authority.

`src/cadrumo/core/_toml.py` is the canonical TOML decoding and recursive-freezing owner. A semantic-map loader should reuse `read_toml` and `freeze_toml`; importing `rtoml` or translating arrays independently would redeclare that boundary. The production registry compiler in `src/cadrumo/domain/calculations/registry/_loader.py` supplies the relevant refusal posture: repeated identities and unequal scalar declarations are collisions, never last-writer-wins merges.

The narrow S42 format is `schema_version`, `fragment_id`, `modelo`, `design_epoch`, plus the existing `SemanticMapRecord` and `SemanticMapEntry` arrays. Filenames use `NNNN-<fragment_id>.toml`, and the suffix must equal the authored identifier. Compilation refuses empty fragments or aggregates, non-TOML and linked members, malformed or unknown fields, duplicate fragment identifiers, cross-fragment design drift, exact record-anchor collisions, export-record-id collisions, exact field-anchor collisions, and export-field-id collisions. Records and entries are canonicalized by their exact semantic keys before constructing the existing `SemanticMap`.

`dev/registry/_semantic_map.py` remains the sole schema home for anchors, entries, records, kinds, and canonical identifiers. `dev/registry/_semantic_map_validation.py` continues to own parser bijection and registry-reference resolution, while `dev/registry/_semantic_map_join.py` continues to own exact source-ordered joining. The loader must not read parser intermediates, snapshots, render profiles, generated layouts, neighbouring mappings, or legacy export trees.

The public development facade exports the existing semantic-map types and one `load_semantic_map` entry point. Real tests must create actual TOML fragments and prove canonical order, strict hydration, every collision class, filename-to-id agreement, and absence of a fallback surface.

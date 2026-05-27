---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
step_id: 'S02'
related:
  - '[[2026-05-27-schema-hardening-m309-standardization-plan]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline `code`. -->

# `schema-hardening-m309-standardization` `P01.S02`

Mechanically split Modelo 309 from a root-level single TOML file into the
generic directory/fragments layout.

- Deleted: `309.toml`
- Created: `309/manifest.toml`
- Created: `309/revisions/2004-y-siguientes/revision.toml`
- Created 11 ordered revision section fragments under `309/revisions/2004-y-siguientes/`

## Description

The split preserved the exact line order and bytes of the original Modelo 309
registry source. The mechanical split script reconstructed all generated
fragments in source order and compared the result with the original `309.toml`
bytes before deleting the single-file source.

No schema semantics, loader behavior, casilla definitions, formulas,
bindings, application links, schedule metadata, construct membership, or
completeness manifest content were changed.

## Tests

Verification is recorded in S03. This step's pre-test guard was the
byte-for-byte reconstruction check before deleting `309.toml`.

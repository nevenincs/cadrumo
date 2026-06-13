---
tags:
  - '#audit'
  - '#rename-corpus-review'
date: '2026-04-18'
modified: '2026-04-18'
related:
  - '[[2026-04-18-rename-corpus-review-research]]'
  - '[[2026-04-18-rename-corpus-review-schema-adr]]'
---

# `rename-corpus-review` Code Review

`RENAME-CORPUS-REVIEW-001 | MEDIUM | Remove the manuals alias migration claim`
The first ADR draft claimed that alias-backed parsing plus canonical
serialization would rewrite local persisted JSON in both `aeat.domain.casillas` and
`aeat.domain.manuals`. That was only true for `casillas`, which has real JSON writers.
`aeat.domain.manuals` has loaders for structured `manual.json` / section JSON but no
production writer for those records, so the ADR overstated the migration story
for stale local manual structures.

Disposition: resolved in the final ADR by dropping legacy-support claims,
explicitly scoping the change to repository-owned files, and documenting stale
local JSON as unsupported after the rename.

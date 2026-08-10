---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:0b54d07c372415733c627553372bea97320c594a5189611e366683c868d64631'
step_id: 'S06'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Define the adjacent non-loader provenance manifest and normalized loader-semantic digest

## Scope

- `dev/registry/`

## Description

- Define strict, frozen target, output-digest, and provenance-manifest models.
- Bind source, semantic-map, parser, generator, target, loader-semantic, and output-file evidence to canonical SHA-256 digests.
- Normalise loader-visible layout semantics with explicit schema-drift refusal.
- Reject noncanonical JSON, duplicate JSON keys and output paths, unsafe paths, links, junctions, empty trees, invalid hashes, and version drift.
- Add a structural red test that rejects legacy-layout lookup or fallback dependencies.
- Obtain independent review after focused tests and static analysis pass.

## Outcome

The non-loader sibling manifest contract is defined only; this step emits, generates, and publishes no export tree. Focused provenance tests passed 4/4; the S02-S06 contract suite passed 32/32; Ruff and basedpyright passed on the owned paths. Independent Luna review found no critical, high, or medium issue.

## Notes

Concurrent Vault CLI actions briefly timed out while scaffolding. Both required records were created and no worktree, index, or peer-owned file was changed to work around that transient contention.

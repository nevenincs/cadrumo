---
generated: true
tags:
  - '#index'
  - '#sync-control-surface'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:fa425683e29a2049ccd1bc4a5bc119ad95492b07137b3d43b62bcbae5c9f8e06'
related:
  - '[[2026-08-08-sync-control-surface-P02-S01]]'
  - '[[2026-08-08-sync-control-surface-P02-S02]]'
  - '[[2026-08-08-sync-control-surface-P02-S04]]'
  - '[[2026-08-08-sync-control-surface-P03-S01]]'
  - '[[2026-08-08-sync-control-surface-adr]]'
  - '[[2026-08-08-sync-control-surface-plan]]'
  - '[[2026-08-08-sync-control-surface-reference]]'
---

# `sync-control-surface` feature index

Auto-generated index of all documents tagged with `#sync-control-surface`.

## Documents

### adr

- `2026-08-08-sync-control-surface-adr` - `sync-control-surface` adr: `Dry-run is a flag on both sync surfaces, and its payload differs by write shape` | (**status:** `accepted`)

### exec

- `2026-08-08-sync-control-surface-P02-S01` - Relocate the recapture divergence computation ahead of the upsert
- `2026-08-08-sync-control-surface-P02-S02` - add the dry-run short-circuit to the filed sweep, returning the divergence set the upsert would introduce without writing
- `2026-08-08-sync-control-surface-P02-S04` - Reuse the verify parity comparison to build the export preview
- `2026-08-08-sync-control-surface-P03-S01` - Define the typed sync-run record carrying surface, resolved scope, completion instant, unit counts and divergence count. SCOPE CORRECTION, one finding rather than three notes. This row's scope clause was authored against an ASSUMED layout and is wrong in three places, so a builder following it lands in an illegal home. The surface axis is a new closed value set, so it is a StrEnum in core rather than a Literal local to the storage package. The atomicity the sibling row requires reaches the secure-object batch writer under adapters persistence, so the record model may live in application while the co-write cannot. And application storage is a namespace container whose own facade states it re-exports nothing by design because exporting there would couple callers to the internal subpackage layout, so a private module directly under it admits only a cross-package private import or a re-export its docstring forbids. The record therefore lives in an application storage subpackage with its own public facade, matching the calc sheets sibling. Two model decisions carry reasons rather than conventions. The success flag is not redundant against the divergence count and inferring either from the other inverts both cases, because a run can finish cleanly having found divergences and can fail partway having found none precisely because it never got far enough to look. And the divergence count is refused at construction when it exceeds the unit count, because a unit the run never reached cannot have been found to diverge. Both counts describe what the run REACHED and never what it intended to reach

### plan

- `2026-08-08-sync-control-surface-plan` - `sync-control-surface` plan

### reference

- `2026-08-08-sync-control-surface-reference` - `sync-control-surface` reference: `grounding`

---
step_id: "S418"
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W04.P21.S418

## Outcome

`SourceMeshError(CoreValidationError)` introduced in
`src/aeat/application/aggregation/_source_mesh.py`. Four bare
`raise ValueError(...)` at lines 89, 91, 119, 121 replaced. Registry entry added
under `REFUSED_SOURCE_MESH_INVARIANT`. Plan step closed.

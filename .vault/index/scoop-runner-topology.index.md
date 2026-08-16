---
generated: true
tags:
  - '#index'
  - '#scoop-runner-topology'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:67decd84df88547770303db2e8a82b39c7caef8485bc32bfe1d9db3202fbae8b'
related:
  - '[[2026-07-22-scoop-runner-topology-adr]]'
  - '[[2026-07-25-scoop-runner-topology-S04]]'
  - '[[2026-07-25-scoop-runner-topology-S05]]'
  - '[[2026-07-25-scoop-runner-topology-plan]]'
---

# `scoop-runner-topology` feature index

Auto-generated index of all documents tagged with `#scoop-runner-topology`.

## Documents

### adr

- `2026-07-22-scoop-runner-topology-adr` - `scoop-runner-topology` adr: `Scoop windows-x86-64 evidence lane runs on a native Windows runner, not the shared Docker daemon` | (**status:** `accepted`)

### exec

- `2026-07-25-scoop-runner-topology-S04` - Record an explicit unaffected-and-why reconciliation against the account-distribution-standard ruling, because this record governs which runner executes the Scoop evidence lane while that record governs where Scoop manifests live, and a reader finding two Scoop decisions with no stated relationship must not have to re-derive the orthogonality
- `2026-07-25-scoop-runner-topology-S05` - Adapt the Scoop acquisition lane to the ADR-ruled native execution, replacing the docker Windows-container preflight and the Container-mode harness invocation with a native Host-mode invocation pinned to the windows-scoop runner label, a preflight asserting AMD64 plus a resolvable Scoop in the lane user's profile, and a per-run Scoop profile reset that keeps acquisitions independent, and update the structural gate to pin the native shape

### plan

- `2026-07-25-scoop-runner-topology-plan` - `scoop-runner-topology` plan

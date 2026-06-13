---
step_id: S666
tags:
  - "#exec"
  - "#codebase-solidification"
date: '2026-06-01'
modified: '2026-06-01'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-31-codebase-solidification-audit]]"
---

# codebase-solidification W26.P58.S666 — Ledger no-untyped-def cluster

## Outcome

Proper annotations added to two private helpers in
`src/aeat/application/modelo/_actions.py`:

- `_load_work_unit_for_calculation(work_units: WorkUnitCatalogue, *, work_unit_id: str) -> WorkUnit`
- `_resolve_registry_snapshot_for_work_unit(work_unit: WorkUnit) -> RegistrySnapshot`

Both types already imported in the file. Both `# type: ignore[no-untyped-def]`
lines removed.

No sibling `no-untyped-def` sites discovered in the same file beyond these two.

Design choice: proper annotation (both parameter and return types are fully
expressible with existing imports).

Allowlist paydown: 2 entries removed.

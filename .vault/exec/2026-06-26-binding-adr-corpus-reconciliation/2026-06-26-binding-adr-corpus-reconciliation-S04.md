---
tags:
  - '#exec'
  - '#binding-adr-corpus-reconciliation'
date: '2026-07-05'
modified: '2026-07-10'
step_id: 'S04'
related:
  - "[[2026-06-26-binding-adr-corpus-reconciliation-plan]]"
---

# REWORK: keep the bindings CLI surface

## Scope

- `record the operator_surface.SourceKind duplicate as superseded by phase 2.1 and CLI vocabulary aligned in phase 2.4`
- `.vault/adr/2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr.md`

## Description

- Reconstruct the execution record for the already-checked S04 row.
- Confirm commit `648f290cb6` reworked `2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr.md`.
- Verify the status block keeps the bindings CLI surface while superseding the duplicate `operator_surface.SourceKind`.

## Outcome

- S04 is backed by landed evidence. The bindings list and preview surface remains
  accepted, while the duplicate `operator_surface.SourceKind` is superseded by
  the phase 2.1 source-kind taxonomy and CLI vocabulary alignment is assigned to
  future phase 2.4.
- No source code or plan checkbox was changed in this reconciliation pass.

## Notes

- Reconstructed on 2026-07-05 because the step was checked without an exec record.
- Evidence command: `git show --stat --oneline 648f290cb6`.

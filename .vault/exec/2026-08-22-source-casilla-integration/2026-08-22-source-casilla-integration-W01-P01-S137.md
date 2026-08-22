---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:901529a48f36e2be33c1aa3e318210be5dc0a53d984902a5bfb66e7655c75e0c'
step_id: 'S137'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---




# project supported modelo calculation workflows from the reconciled live operator surface

## Scope

- `src/cadrumo/application/operator_surface`

## Description

- Project supported calculation workflows from reconciled live operator leaves.
- Preserve canonical CLI paths as evidence beside exact subject-leaf command identities.
- Enforce strict frozen models, deterministic ordering, and duplicate refusal.
- Exclude absent or unrelated live leaves without importing entrypoint owners.
- Publish the application-owned catalogue through the operator-surface facade.

## Outcome

The application layer now provides a strict catalogue for live CLI calculation
workflows. Semantic eligibility narrows the reconciliation but never declares
command existence: a workflow is supported only while its exact live leaf and
canonical path remain present in `OperatorSurfaceReconciliation`.

## Notes

The repository-wide import-hygiene scanner reached an unrelated existing TUI
migration refusal for `cadrumo.adapters.inbound.tui._recovery_words_screen`.
The new application module imports no entrypoint package; focused Ruff,
compilation, reconciliation, and catalogue tests pass.

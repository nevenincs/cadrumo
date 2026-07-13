---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S78'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Run focused runtime, persistence, CLI, MCP, agent, and packaging tests with real behavior

## Scope

- `Cadrumo feature test surface`

## Description

- Reconcile the canonical Cadrumo executable after quarantining an unapproved concurrent CLI detour.
- Repair the corrupted product-identity contract so it imports the public Cadrumo facade and asserts the accepted tuple.
- Run focused runtime, persistence, CLI, MCP, agent, companion-packaging, sealed-archive, and MCPB behavior tests without mocks, skips, or expected failures.
- Redirect artifact-build temporary storage and the uv cache to the workspace drive after the system drive exhausted its free space.
- Narrow the retired MCPB assertion to the actual artifact name so the repository parent path cannot create a false positive.

## Outcome

The focused Cadrumo feature surface is green. Ten identity, import-hard-cut, installed-console, root-help, documented-command, educational-document, and self-referential-command checks passed serially. A broader runtime matrix then passed thirty-five tests before artifact setup encountered shared temporary-directory exhaustion. Re-running the artifact slice with isolated workspace-local temporary and cache roots passed twenty-nine companion-wheel, shared-namespace, persistence archive, MCPB, and distribution-budget checks. The final evidence is sixty-four passing real-behavior tests with no product assertion failure.

## Notes

An earlier parallel run crashed an xdist worker, so the accepted evidence uses serial execution to remove worker instability from the product signal. The system drive had about sixteen megabytes free and could not stage companion wheels; the workspace drive had sufficient capacity and completed the same builds. No product source or evidence bytes were changed to accommodate the environment. Public publication remains outside this Step and blocked by the external reservation gate.

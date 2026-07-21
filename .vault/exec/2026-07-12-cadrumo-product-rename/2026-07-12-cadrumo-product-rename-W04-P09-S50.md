---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S50'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Regenerate the marketplace manifest and Cadrumo plugin subtree from the changed authority

## Scope

- `packaging/marketplace generated output`

## Description

- Regenerate the marketplace manifest and ignored served-plugin tree from the committed S48 authority.
- Emit only the `plugins/cadrumo` identity with the pinned Cadrumo distribution and MCP launcher.
- Compare a clean temporary emission byte-for-byte and repeat the in-place emission to prove idempotence.
- Reject former plugin, distribution, executable, URI, and environment identities from generated output.

## Outcome

The checked-in marketplace manifest now points exclusively to
`./plugins/cadrumo`. The generated served plugin is Cadrumo `0.1.1`, launches
`cadrumo-mcp` from `cadrumo[agent]==0.1.1`, and exposes only `CADRUMO_MCP_*`
product environment keys. Fourteen focused generator tests and Ruff pass.

## Notes

The served `plugins/cadrumo` subtree remains intentionally ignored and
uncommitted under the marketplace packaging contract; it was regenerated for
the following live-validator step. Existing README and `.gitignore` working
changes were present before S50 and were preserved outside this commit.

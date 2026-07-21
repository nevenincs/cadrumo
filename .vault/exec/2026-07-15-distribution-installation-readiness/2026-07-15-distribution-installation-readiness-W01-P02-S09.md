---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S09'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Prove installed MCP execution succeeds without checkout imports or executable paths

## Scope

- `src/cadrumo/entrypoints/mcp/tests/test_installed_cli_resolution.py`

## Description

- Build the committed command-bearing wheel and both mandatory corpus companion wheels.
- Install the complete cohort with the `agent` extra into a fresh stdlib virtual environment.
- Launch the installed absolute `cadrumo-mcp` console script from a directory outside the
  checkout.
- Remove `PYTHONPATH` and every product executable directory from `PATH`.
- Call the public MCP `execute` tool and require the installed server to execute the sibling
  `aeat` console script successfully.

## Outcome

- The real three-wheel cohort built and installed into a new environment.
- Both installed console scripts existed in the same environment.
- Neither `aeat` nor `cadrumo-mcp` was discoverable through the child `PATH`.
- The installed MCP server initialized as `cadrumo` and returned the live operator-surface
  contract through its sibling installed CLI.
- Ruff, ty, Python compilation, and the real serial integration test passed.

## Notes

- The test uses a pristine `git archive HEAD` build root so unrelated uncommitted source files
  cannot satisfy the installed-artifact proof.
- The passing integration run took 339.90 seconds and built companion wheels of 76.7 MB and
  62.5 MB before executing the protocol assertion.

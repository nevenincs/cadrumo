---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S59'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Retarget agent-harness evaluation to cadrumo-mcp

## Scope

- `.github/workflows/agent-harness-eval.yml`

## Description

- Rename the workflow and job evidence labels to Cadrumo and identify the evaluated server as `cadrumo-mcp`.
- Retarget live harness, identity, confirmation, replay, faithfulness, and provenance fixtures to canonical `cadrumo_*` tool identities.
- Use the live abbreviated `cadrumo_modelo_ivaw_balance` name where the client-visible budget contract requires it.
- Reject former executable, tool-prefix, resource-scheme, and source-path identities across the evaluated surface.

## Outcome

The standing agent-harness gate now records Cadrumo evidence and exercises the
real Cadrumo MCP server and tool namespace without a former-product alias.

## Notes

- Thirty-two focused real harness tests passed; Ruff and `actionlint` passed.
- YAML parsing and structural checks confirmed the Cadrumo workflow label, `cadrumo-mcp` job evidence, canonical source paths, and absence of former executable/path residue.
- The first replay run exposed the intentionally abbreviated IVA wallet tool name; the fixture was corrected to the live dispatch authority and the rerun passed.
- Formal review found that the live test still launched the module through `python -c`; it now spawns the real `cadrumo-mcp` console script and the focused live test passes.

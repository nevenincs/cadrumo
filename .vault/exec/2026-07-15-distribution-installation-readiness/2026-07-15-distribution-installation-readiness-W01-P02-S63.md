---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S63'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Harden installed oracles for direct MCP dispatch exact legal grounding resource identity and diagnostic failure

## Scope

- `dev/packaging`
- `src/cadrumo/entrypoints/mcp`

## Description

- Activate the public `modelo-lifecycle` MCP toolset and call `cadrumo_modelo_work_calculate` directly.
- Require the target observation to cite `ley-27-2014:art-29` and the established manual source.
- Require calculation, observations, and resource-content URIs to identify the exact persisted revision.
- Fail setup and observation commands on warning or error diagnostics instead of accepting warning envelopes.
- Advertise the actual envelope emitted by direct MCP tools as their SDK output schema.

## Outcome

- The real MCP client now accepts and validates direct-tool structured content against the advertised schema.
- The complete source-environment MCP itinerary passed through the direct calculation tool with `DP200014:00562=23000.00`.
- Retained evidence records revision `44dfa6ee495e923f4811f011122b8f1f8880d4983867de46bbcbf038e34553fd`, formula `modelo-200-cuota-integra`, and the exact observation resource.
- Ruff and ty passed; nineteen MCP schema, thinning, and size-budget tests passed.

## Notes

- The first real direct calculation exposed that per-verb tools advertised an inner-result schema while returning the shared envelope. The MCP SDK correctly rejected that mismatch, so the production schema adapter was repaired before the oracle could pass.
- One source run hit the existing 120-second mutation timeout during work creation; a clean rerun completed in 134 seconds overall with every individual call inside its tier limit.

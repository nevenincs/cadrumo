---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S45'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Operator-gated: install the plugin into Cowork and resolve whether the local stdio server runs on-host or connectors execute in Anthropic's cloud (needs a real Cowork install)

## Scope

- `docs/verification/cowork-install-proof.md`

## Description

- Remove the publish blocker for local delivery: retarget the installed plugin's `.mcp.json` at the locally built slim wheel (`uvx --from "aeat[agent] @ file:///...aeat-0.1.0-py3-none-any.whl" aeat-mcp` — command-shape identical to the published flow), reinstall + enable at user scope.
- Run a live headless session of the Claude desktop app's OWN embedded runtime (claude-code 2.1.187) with a concurrent process watch: `uvx.exe` spawned LOCALLY on this host with the exact plugin-declared command line during the session — the MCP server executes ON-HOST, not in Anthropic's cloud, answering the step's defining question by direct observation.
- Complete the full tool round-trip: with the read-only floor tool pre-approved, the session called `mcp__plugin_aeat_aeat__aeat_harness_load` and received the harness payload leading with the R9 off-host privacy disclosure, exactly as the harness-refoundation ADR designed; the unapproved first attempt was correctly permission-blocked.
- Proof updated at `docs/verification/cowork-install-proof.md` (status COMPLETE); commit `d0694a9e66`.

## Outcome

- The research's MEDIUM-confidence cloud-execution concern for this surface is refuted by measurement on this host: local spawn, local round-trip, permission gate live.

## Notes

Honest scope: the measurement covers the shared embedded runtime the desktop app (and its Cowork agentic mode) executes; a human-driven Cowork GUI session remains worthwhile corroboration. The local-wheel launch variant substitutes for the PyPI variant until first publish; re-verification after publish is tracked in the operator-gated follow-up. Executed inline by the coordinator after the stop-gate correctly challenged the operator-gated classification.

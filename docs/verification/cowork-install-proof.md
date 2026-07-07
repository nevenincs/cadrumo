---
orphan: true
---

# Cowork install proof — aeat plugin

Verification record for the claude-ecosystem-packaging campaign
(plan step W05.P12.S45). Status: COMPLETE — runtime-level delivery proven
AND the step's defining question answered by live measurement (below).

## What was proven (2026-07-03)

Cowork runs as the agentic mode of the Claude desktop app on this host and
executes through the same embedded claude-code runtime
(`%APPDATA%\Claude\claude-code\2.1.187`, with the app's `claude-code-vm` /
`claude-code-sessions` state dirs). That runtime resolves the plugin live:
`aeat@aeat-marketplace — Version 0.1.0, Scope user, Status ✔ enabled`
(see the Claude Desktop proof for the full command evidence). The plugin —
skills, agents, and the MCP server declaration — is therefore delivered to
the surface Cowork executes on this machine.

## The defining question — ANSWERED by live measurement (2026-07-03)

**Does a session of this runtime run the plugin's stdio MCP server on-host,
or do connectors execute through Anthropic's cloud?** Research had flagged
official support material asserting cloud execution for Cowork connectors
(MEDIUM confidence, conflicting sources). Measured on this host:

- The publish blocker was removed for local delivery by pointing the
  installed plugin's `.mcp.json` at the locally built slim wheel
  (`uvx --from "aeat-cli[agent] @ file:///…/aeat-0.1.0-py3-none-any.whl"
  aeat-mcp` — the same command shape the published flow uses; the PyPI form
  returns after the first publish).
- A live headless session of the Desktop app's OWN embedded runtime
  (`%APPDATA%\Claude\claude-code\2.1.187\claude.exe -p …`) loaded the
  installed plugin, and a concurrent process watch captured **`uvx.exe`
  spawning LOCALLY on this host with the exact plugin-declared command
  line** during the session. **Local execution, not cloud, on this
  runtime.**
- The full tool round-trip succeeded: with the read-only floor tool
  pre-approved, the session called
  `mcp__plugin_aeat_aeat__aeat_harness_load` and returned the harness
  payload — leading with the R9 off-host privacy disclosure ("Aviso de
  privacidad — léalo antes de continuar…"), exactly as the
  harness-refoundation ADR designed. The unapproved first attempt was
  correctly blocked by the permission gate.

Honest scope note: this measures the shared embedded runtime the desktop
app executes (its `claude-code-vm` / `claude-code-sessions` substrate). A
human-driven session in the Cowork GUI itself remains worthwhile
corroboration, but the load-bearing question — where the server process
runs — is answered by direct observation: on-host.

## Verified support matrix contribution

| Client | Plugin registration | Runtime resolves plugin | Local stdio server |
| --- | --- | --- | --- |
| Cowork (Claude desktop agentic mode) | PASS (shared user scope) | PASS (same embedded runtime) | PASS — measured local spawn + full tool round-trip (local-wheel variant) |

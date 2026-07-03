# Cowork install proof — aeat plugin (partial)

Verification record for the claude-ecosystem-packaging campaign
(plan step W05.P12.S45). Status: PARTIAL — runtime-level delivery proven;
the step's defining question remains open.

## What was proven (2026-07-03)

Cowork runs as the agentic mode of the Claude desktop app on this host and
executes through the same embedded claude-code runtime
(`%APPDATA%\Claude\claude-code\2.1.187`, with the app's `claude-code-vm` /
`claude-code-sessions` state dirs). That runtime resolves the plugin live:
`aeat@aeat-marketplace — Version 0.1.0, Scope user, Status ✔ enabled`
(see the Claude Desktop proof for the full command evidence). The plugin —
skills, agents, and the MCP server declaration — is therefore delivered to
the surface Cowork executes on this machine.

## What remains open (the step's defining question)

**Does a Cowork session run the plugin's local stdio MCP server on-host, or
do Cowork connectors execute through Anthropic's cloud?** Research flagged
official support material asserting cloud execution for Cowork connectors
(MEDIUM confidence, conflicting sources). If cloud, the aeat server — which
must sit beside the on-host encrypted store — would be skills-only in
Cowork sessions. This is answerable only by a live, human-driven Cowork
session after the first PyPI publish makes the server launchable
(`uvx --from aeat==0.1.0 aeat-mcp`):

1. Publish the slim wheel (RELEASING.md step 4).
2. Open Cowork, start a session, invoke an aeat skill that calls an MCP
   tool (e.g. the orientation flow from `regularizar-atrasos`).
3. Observe whether `aeat-mcp` spawns as a local process
   (`Get-Process | Where-Object { $_.CommandLine -match 'aeat-mcp' }`)
   during the call.
4. Record the answer here and in the support matrix; the userdocs state
   whatever this measures — never the aspiration.

## Verified support matrix contribution

| Client | Plugin registration | Runtime resolves plugin | Local stdio server |
| --- | --- | --- | --- |
| Cowork (Claude desktop agentic mode) | PASS (shared user scope) | PASS (same embedded runtime) | OPEN — cloud-vs-local question; measure live after first publish |

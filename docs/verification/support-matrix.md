# Verified support matrix — aeat Claude plugin

The measured — never aspirational — client support state for the aeat
plugin. This is what the user documentation may claim. Campaign
claude-ecosystem-packaging, plan step W05.P13.S47; measurements of
2026-07-03 on Windows 11, Claude Code CLI 2.1.199, Claude desktop app with
embedded claude-code runtime 2.1.187. Per-client evidence lives in the
sibling install-proof documents.

| Capability | Claude Code CLI | Claude Desktop | Cowork (desktop agentic mode) |
| --- | --- | --- | --- |
| Marketplace add + plugin install | PASS (live) | PASS (shared user-scope registry) | PASS (shared user-scope registry) |
| Plugin resolved by the client's runtime | PASS | PASS (app's own embedded binary, live) | PASS (same embedded runtime) |
| Disabled-by-default + persona configure surface | PASS (observed at install) | PASS (same plugin system) | PASS (same plugin system) |
| Local stdio `aeat-mcp` server spawns | PASS | PASS | PASS — measured local `uvx` spawn during a live session; NOT cloud |
| Full MCP tool round-trip (harness floor) | PASS (R9 privacy disclosure returned first) | PASS (same runtime measurement) | PASS (same runtime measurement) |
| Permission gate on unapproved tool calls | PASS (observed live) | PASS (same runtime) | PASS (same runtime) |

## Launch-variant note — RESOLVED (2026-07-03, first publish)

`aeat-cli 0.1.0` is live on PyPI (published via the Trusted Publishing
workflow, run 28675038482; 41 MB wheel, zero corpus binaries). The matrix's
server rows are re-verified against the PUBLISHED pin: the reinstalled
plugin's `.mcp.json` launches `uvx --from "aeat-cli[agent]==0.1.0"
aeat-mcp`, the package cold-resolves from the index (79 packages), and a
live session completed the harness floor round-trip (R9 privacy disclosure
returned first) through the published chain. The earlier local-wheel
variant is retired.

## Out of scope of this matrix

- claude.ai web: no local process host — the plugin's skills surface may
  load, the local server cannot. Not measured; do not claim it.
- The full golden `regularizar-atrasos` itinerary through the installed
  plugin (W05.P13.S46) is the remaining end-to-end scenario measurement;
  the harness floor round-trip above is the transport-level proof it
  builds on.

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

## Launch-variant note

The measured server-launch used the local-preview variant
(`uvx --from "aeat[agent] @ file:///…/aeat-0.1.0-py3-none-any.whl"
aeat-mcp`) because the `aeat` package is not yet on PyPI. The published
variant (`uvx --from "aeat-cli[agent]==<version>" aeat-mcp`) is command-shape identical
and becomes verifiable the moment the first publish lands (RELEASING.md
name-claim sequencing). Re-confirm this matrix's server rows against the
PyPI variant after the first release.

## Out of scope of this matrix

- claude.ai web: no local process host — the plugin's skills surface may
  load, the local server cannot. Not measured; do not claim it.
- The full golden `regularizar-atrasos` itinerary through the installed
  plugin (W05.P13.S46) is the remaining end-to-end scenario measurement;
  the harness floor round-trip above is the transport-level proof it
  builds on.

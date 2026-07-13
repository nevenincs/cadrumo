---
orphan: true
---

# Verified support matrix — historical plugin identifier

The measured — never aspirational — client support state for the former aeat
plugin. This is historical campaign evidence, not current user guidance.
Campaign claude-ecosystem-packaging, plan step W05.P13.S47; measurements of
2026-07-03 on Windows 11, Claude Code CLI 2.1.199, Claude desktop app with
embedded claude-code runtime 2.1.187. Per-client evidence lives in the
sibling install-proof documents.

**Historical naming note.** This record preserves evidence from before the
Cadrumo product rename. It is not current installation guidance. Current
release material names the plugin `cadrumo` and its Model Context Protocol
(MCP) server `cadrumo-mcp`. The human-facing `aeat` command-line interface
(CLI) is unchanged. This record does not establish current public marketplace or
package availability. Legacy plugin and marketplace identifiers below are quoted
evidence only.

| Capability | Claude Code CLI | Claude Desktop | Cowork (desktop agentic mode) |
| --- | --- | --- | --- |
| Marketplace add + plugin install | PASS (live) | PASS (shared user-scope registry) | PASS (shared user-scope registry) |
| Plugin resolved by the client's runtime | PASS | PASS (app's own embedded binary, live) | PASS (same embedded runtime) |
| Disabled-by-default + persona configure surface | PASS (observed at install) | PASS (same plugin system) | PASS (same plugin system) |
| Local stdio `cadrumo-mcp` server spawns | PASS | PASS | PASS — measured local `uvx` spawn during a live session; NOT cloud |
| Full MCP tool round-trip (harness floor) | PASS (R9 privacy disclosure returned first) | PASS (same runtime measurement) | PASS (same runtime measurement) |
| Permission gate on unapproved tool calls | PASS (observed live) | PASS (same runtime) | PASS (same runtime) |

## Launch-variant note — publication pending

Public PyPI availability for `cadrumo` is not currently evidenced. Do not claim
that a user can install the package, its companion distributions, or the plugin
from public indexes. Before publishing installation guidance, verify the public
package names, the `cadrumo-mcp` launch command, and a clean end-to-end plugin
installation. The `aeat` command remains the human CLI after installation.

## Out of scope of this matrix

- claude.ai web: no local process host — the plugin's skills surface may
  load, the local server cannot. Not measured; do not claim it.
- The full golden `regularizar-atrasos` itinerary through the installed
  plugin (W05.P13.S46) is the remaining end-to-end scenario measurement;
  the harness floor round-trip above is the transport-level proof it
  builds on.

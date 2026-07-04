---
orphan: true
---

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

## Launch-variant note — RESOLVED (2026-07-04, v0.1.1 full release)

The complete distribution is live on PyPI with no size grant:
`aeat-cli 0.1.1` (41.3 MB slim wheel), `aeat-data-manuals 0.1.1` (76.7 MB)
and `aeat-data-official 0.1.1` (62.4 MB) — the corpus companions split
along the directory seam so each clears the 100 MB cap. End-to-end proof
on a fresh venv from the index only: `pip install
"aeat-cli[corpus-sources,agent]"` resolves all three, and
`aeat app registry verify` runs byte-exact clean (exit 0; 46 modelos,
518 application links) with the binaries resolved through the `aeat_data`
namespace seam. The installed plugin pins
`uvx --from "aeat-cli[agent]==0.1.1" aeat-mcp`; the harness floor
round-trip through the published chain was verified live on 0.1.0 and the
transport is unchanged. Note: 0.1.0's `corpus-sources` extra is
unresolvable on the index (it pinned the never-published single
`aeat-data`); 0.1.1 is the first fully-resolvable release — consider
yanking 0.1.0 on PyPI.

## Out of scope of this matrix

- claude.ai web: no local process host — the plugin's skills surface may
  load, the local server cannot. Not measured; do not claim it.
- The full golden `regularizar-atrasos` itinerary through the installed
  plugin (W05.P13.S46) is the remaining end-to-end scenario measurement;
  the harness floor round-trip above is the transport-level proof it
  builds on.

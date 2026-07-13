---
orphan: true
---

# Historical marketplace install record — pre-Cadrumo plugin identifier

Historical verification for the claude-ecosystem-packaging campaign,
2026-07-04. It measured a public delivery chain end to end, with no local paths
or pre-staged wheels. It does not establish current public availability.

**Historical naming note.** This record preserves evidence from before the
Cadrumo product rename. It is not current installation guidance. Current
release material names the plugin `cadrumo` and its Model Context Protocol
(MCP) server `cadrumo-mcp`. The human-facing `aeat` command-line interface
(CLI) is unchanged. This record does not establish current public marketplace or
package availability. Legacy plugin and marketplace identifiers below are quoted
evidence only.

## The chain at measurement time

1. **Public GitHub marketplace at measurement time** — `nevenincs/neve-marketplace` (the `neve`
   namespace; 59 tracked files: `.claude-plugin/marketplace.json` + the
   generated `plugins/aeat/` tree, 34 skills + 7 agents).
2. **One-command add + install** (Claude Code CLI):
   - `claude plugin marketplace add nevenincs/neve-marketplace` →
     "Successfully added marketplace: neve".
   - `claude plugin install aeat@neve` → "Successfully installed plugin:
     aeat@neve (scope: user)"; disabled-by-default surfaced as designed.
   - `claude plugin enable aeat@neve` → enabled.
3. **PyPI-launched local server at measurement time** — the installed plugin's
   `.mcp.json` ran `uvx --from "cadrumo[agent]==0.1.1" cadrumo-mcp`, resolving
   the package from the index.
4. **Live tool round-trip** — a session of the Claude desktop app's embedded
   runtime, restricted to `mcp__plugin_aeat_aeat__*`, called the harness floor
   tool and received the payload leading with the R9 off-host privacy
   disclosure ("Aviso de privacidad — léalo antes de continuar…").

At measurement time, every hop was a public artifact that a user with `uv`
could reproduce: `add nevenincs/neve-marketplace` → `install aeat@neve` → the
server boots from PyPI. This was evidence that a third party could install and
run the assistant at that time.

## Addressing

At measurement time, plugins under this marketplace used `<plugin>@neve`;
the measured address was `aeat@neve`. The
marketplace name (`neve`) is independent of its serving repo
(`nevenincs/neve-marketplace`) and is the stable ecosystem namespace future
plugins join as additional `plugins[]` entries.

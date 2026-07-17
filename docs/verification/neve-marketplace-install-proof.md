---
orphan: true
---

# Public marketplace install proof — aeat@neve

Live verification for the claude-ecosystem-packaging campaign, 2026-07-04.
Proves the FULLY PUBLIC delivery chain end to end — no local paths, no
pre-staged wheels.

## The chain, all public

1. **Public GitHub marketplace** — `nevenincs/neve-marketplace` (the `neve`
   namespace; 59 tracked files: `.claude-plugin/marketplace.json` + the
   generated `plugins/aeat/` tree, 34 skills + 7 agents).
2. **One-command add + install** (Claude Code CLI):
   - `claude plugin marketplace add nevenincs/neve-marketplace` →
     "Successfully added marketplace: neve".
   - `claude plugin install aeat@neve` → "Successfully installed plugin:
     aeat@neve (scope: user)"; disabled-by-default surfaced as designed.
   - `claude plugin enable aeat@neve` → enabled.
3. **PyPI-launched local server** — the installed plugin's `.mcp.json` runs
   `uvx --from "aeat-cli[agent]==0.1.1" aeat-mcp`, resolving the published
   package from the index.
4. **Live tool round-trip** — a session of the Claude desktop app's embedded
   runtime, restricted to `mcp__plugin_aeat_aeat__*`, called the harness floor
   tool and received the payload leading with the R9 off-host privacy
   disclosure ("Aviso de privacidad — léalo antes de continuar…").

Every hop is a public artifact any user with `uv` can reproduce:
`add nevenincs/neve-marketplace` → `install aeat@neve` → the server boots from
PyPI. This is the first proof that a third party (not this dev machine) could
install and run the assistant.

## Addressing

Plugins under this marketplace are `<plugin>@neve`. Today: `aeat@neve`. The
marketplace name (`neve`) is independent of its serving repo
(`nevenincs/neve-marketplace`) and is the stable ecosystem namespace future
plugins join as additional `plugins[]` entries.

# Claude Desktop install proof — aeat plugin

Live verification record for the claude-ecosystem-packaging campaign
(plan step W05.P12.S44). Host: Windows 11 with the Claude desktop app
installed (`%APPDATA%\Claude`, embedded claude-code runtime 2.1.187),
2026-07-03.

## What was proven

1. **Shared registration surface.** The Claude desktop app embeds the
   claude-code runtime (`%APPDATA%\Claude\claude-code\2.1.187\claude.exe`)
   and reads the same user-scope plugin registry
   (`~/.claude/plugins/installed_plugins.json`) the CLI writes. The plugin
   installed from the marketplace in the Claude Code proof is therefore the
   same artifact the desktop app loads.
2. **Enable.** `claude plugin enable aeat@aeat-marketplace` →
   "Successfully enabled plugin: aeat (scope: user)".
3. **The desktop app's own runtime resolves the plugin.** Executed the
   embedded binary directly:
   `& "$env:APPDATA\Claude\claude-code\2.1.187\claude.exe" plugin list`
   reports, verbatim: `aeat@aeat-marketplace — Version: 0.1.0, Scope: user,
   Status: ✔ enabled`. The plugin (skills, agents, MCP server declaration)
   is delivered to the desktop app at the runtime level.

## What remains, and on what

- **Server start via uvx** — identical residual to the Claude Code proof:
  the plugin's `.mcp.json` launches `uvx --from aeat==0.1.0 aeat-mcp`,
  unresolvable until the first PyPI publish (RELEASING.md name-claim
  sequencing; operator-gated). Re-verify after publish.
- **In-app UI session confirmation** — a human opening the desktop app and
  confirming the plugin's tools surface in a live chat/Cowork session. The
  runtime-level proof above is the strongest evidence obtainable without
  driving the native app UI.

## Verified support matrix contribution

| Client | Plugin registration | Runtime resolves plugin | Local stdio server |
| --- | --- | --- | --- |
| Claude Desktop (embedded 2.1.187) | PASS (shared user scope) | PASS (live, app's own binary) | Pending first publish (uvx) |

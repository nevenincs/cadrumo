---
orphan: true
---

# Claude Code install proof — historical plugin identifier

Live verification record for the claude-ecosystem-packaging campaign
(plan step W05.P12.S43). Client: Claude Code CLI 2.1.199 on Windows 11,
2026-07-03. Every command below ran for real; outputs are quoted from the
live run.

**Historical naming note.** This record preserves evidence from before the
Cadrumo product rename. It is not current installation guidance. Current
release material names the plugin `cadrumo` and its Model Context Protocol
(MCP) server `cadrumo-mcp`. The human-facing `aeat` command-line interface
(CLI) is unchanged. This record does not establish current public marketplace or
package availability. Legacy plugin and marketplace identifiers below are quoted
evidence only.

## What was proven

1. **Generate.** `aeat app agent --layout plugin -o <dir>` materialised the
   plugin from the shipped harness source: 34 skills, 7 agents, aeat v0.1.0.
2. **Validate.** `claude plugin validate --strict` passed on the plugin tree
   AND on the composed marketplace tree (the `packaging/marketplace`
   manifest + the generated plugin under `plugins/aeat`).
3. **Marketplace add.** `claude plugin marketplace add <marketplace-dir>` →
   "Successfully added marketplace: aeat-marketplace".
4. **Install.** `claude plugin install aeat@aeat-marketplace` →
   "Successfully installed plugin: aeat@aeat-marketplace (scope: user)".
   Two designed behaviours surfaced exactly as decided:
   - `defaultEnabled: false` — the client reported the plugin installs
     disabled and named the enable command;
   - the persona `userConfig` option was detected — "1 userConfig option not
     yet set", configurable via `/plugin configure` or `--config KEY=VALUE`.
5. **Server starts (dev-env proof).** The stdio `cadrumo-mcp` server passes the
   real-client handshake conformance tests (initialize / tools-list / call
   round-trip): 2 passed.

## What remains blocked, and on what

The installed plugin's `.mcp.json` launches the server as
`uvx --from cadrumo==0.1.0 cadrumo-mcp`. Until the first `cadrumo` wheel is published
to PyPI (RELEASING.md, name-claim sequencing — an operator-gated step
needing a PyPI account and scoped token), `uvx` cannot resolve that
requirement on any machine, so the end-to-end
installed-plugin-starts-the-server link is unverifiable by design. The
moment the wheel is on PyPI, re-run: enable the plugin, start Claude Code,
and confirm the historical `aeat` plugin's `cadrumo-mcp` tools load; then update this
record.

## Verified support matrix contribution

| Client | Marketplace install | Plugin config UX | Local stdio server |
| --- | --- | --- | --- |
| Claude Code CLI | PASS (live) | PASS (live) | Handshake PASS from dev env; uvx path pending first publish |

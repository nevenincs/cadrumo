---
tags:
  - '#audit'
  - '#engineering-hygiene'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:7c06b41e68b75e4237eb821504ecf9d2598a032b13c9950160ed4d2ce8a5c7c2'
related:
  - "[[2026-08-24-engineering-hygiene-gate-and-environment-reference]]"
---
# `engineering-hygiene` audit: `reconciliation review`

## Scope

Independent review of the validator ratchet correction, core architecture gate enrolment, isolated Vaultspec MCP launch, generated provider configuration, and Windows install guard represented by commits `fdd660cc8d3`, `7118c48974b`, and `96313143263` plus the current generated output diff.

## Findings

### install-reader-race | high | the install preflight still has a reader time-of-check/time-of-use window

The process inventory in `justfile:71` runs before `uv pip install`. The named mutex excludes another installer but not a new project-venv reader, so a process can still start after inventory and hold an extension module during mutation. Isolating the long-lived Vaultspec MCP service removes the repeatedly observed chronic reader and the guard prevents mutation when current owners exist, but neither is a complete shared-reader/exclusive-writer protocol.

### generated-mcp-enrolment | high | provider outputs must land with the canonical tool-mode source

The canonical `.vaultspec/workspace.json` and MCP descriptor select tool mode, while the owning sync produced `uvx --from vaultspec-core python -m vaultspec_core.mcp_server.app` in `.mcp.json`, `.agents/mcp_config.json`, and `.codex/config.toml`. Those generated files remain worktree changes. A commit containing only the canonical source would leave a clean checkout on the old project-venv launch until another operator runs sync.

## Recommendations

Land the generated provider outputs atomically with the canonical tool-mode source. Treat the current Windows guard as fail-closed protection for existing readers, not as proof that future readers are excluded. A follow-on architecture decision is required before expanding every project-venv command into a shared-reader/exclusive-writer lease protocol; that broader command-surface change should not be smuggled into this hygiene repair.

### validator-ratchet-extraction | low | no findings

Independent review found the projection-endpoint extraction behavior-preserving, correctly contained within the registry package, equivalently typed, and covered by the focused projection and reviewability tests. No remediation is required.


---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-17'
step_id: 'S44'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Operator-gated: install the plugin into Claude Desktop and confirm the local server executes (needs a real Claude Desktop install)

## Scope

- `docs/verification/claude-desktop-install-proof.md`

## Description

- Detect the Claude desktop app installed on this host (`%APPDATA%\Claude`, embedded claude-code 2.1.187 runtime, `claude-code-vm`/`claude-code-sessions` state).
- Establish the shared registration surface: the desktop app's embedded runtime reads the same user-scope plugin registry the marketplace install wrote in S43.
- Enable the plugin (`claude plugin enable aeat@aeat-marketplace` -> enabled, scope user).
- Prove delivery with the app's OWN binary: executing the embedded `claude.exe plugin list` reports `aeat@aeat-marketplace — Version 0.1.0, Scope user, Status enabled` live.
- Record the proof at `docs/verification/claude-desktop-install-proof.md`; commit `a39ad4cac1`.

## Outcome

- The plugin (skills, agents, MCP server declaration) is delivered to Claude Desktop at the runtime level — the strongest evidence obtainable without driving the native app UI.

## Notes

Residuals disclosed in the proof document: the uvx server-start link rides the first PyPI publish (identical to S43's residual, tracked operator-gated), and an in-app UI session confirmation remains a human step. S45 (Cowork) is recorded as PARTIAL in `docs/verification/cowork-install-proof.md` — same runtime-level delivery proven, but its defining cloud-vs-local MCP question stays open with the live measurement procedure documented; the step checkbox stays open.

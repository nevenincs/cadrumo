---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-17'
step_id: 'S43'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Install the plugin from the marketplace into the Claude Code CLI and confirm the local stdio aeat-mcp server runs (the confirmed floor)

## Scope

- `docs/verification/claude-code-install-proof.md`

## Description

- Materialise the plugin live (`aeat app agent --layout plugin`), compose the marketplace tree from the landed `packaging/marketplace` manifest plus the generated plugin, strict-validate both, register the marketplace with the real Claude Code CLI 2.1.199, and install: `claude plugin install aeat@aeat-marketplace` succeeded (user scope).
- Observe both designed install behaviours live: `defaultEnabled: false` (installs disabled, enable command named) and the persona `userConfig` option detected and configurable.
- Prove the stdio server itself: the real-client MCP handshake conformance tests pass (2 passed).
- Record the proof at `docs/verification/claude-code-install-proof.md`; commit `557d4ba949`.

## Outcome

- The Claude Code floor is verified live end-to-end EXCEPT the final uvx link: the installed `.mcp.json` launches `uvx --from aeat==0.1.0 aeat-mcp`, which cannot resolve until the first wheel is published to PyPI.

## Notes

The residual link is operator-gated by design (PyPI account + scoped token; RELEASING.md name-claim sequencing). The proof document carries the re-run instruction for after the first publish. Executed inline by the coordinator during the executor-fleet rate-limit window.

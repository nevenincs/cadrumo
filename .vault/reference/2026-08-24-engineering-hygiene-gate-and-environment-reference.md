---
tags:
  - '#reference'
  - '#engineering-hygiene'
date: '2026-08-24'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:084f7fde71dfc248fdf4487b6d9d0148aa54c231049b448e1feeca2ef1f2e7bf'
related:
  - "[[2026-08-18-profile-password-custody-storage-custody-green-sweep-audit]]"
---

# `engineering-hygiene` reference: `gate and environment reconciliation`

The hygiene findings were checked against the current tree, the accepted dependency-provisioning and size-budget decisions, the static-gate harness, and live Windows process ownership.

## Summary

Removing the blank line between the failure accumulator and its first loop preserves an identical Python AST and restores the pin without increasing a tally.

Together they collect 67 tests covering facade-only cross-package imports, shim and forwarding-layer drift, dangling first-party imports, orphaned re-export bridges, and facade exports whose committed definitions disappeared. Before this reconciliation they were reachable through broad dev tests but absent from both `prek.toml` and `dev.quality.suite.GATES`.

The environment corruption is a writer/readers race. `just install` mutates the shared project `.venv`, while canonical Vaultspec configuration selected `dev` mode for the long-lived `vaultspec-core` MCP server. A live Windows inventory found many resident MCP and pytest processes running executables from that environment. The recorded uv failure removes ordinary distribution files before Windows refuses replacement of a held extension module, leaving a partially installed distribution. Additive installation avoids pruning but cannot make that replacement atomic.

The durable boundary is to launch resident Vaultspec MCP servers in isolated `uvx` tool environments, generated from `.vaultspec/workspace.json`, and to keep provider configuration derived through `vaultspec-core sync`. The Windows install recipe additionally serializes writers with a per-environment mutex and refuses before mutation whenever a process still uses the target environment. It reports ownership and never terminates peer processes. Canonical worktree-provisioning guidance uses `just bootstrap`, retaining the accepted additive install path.

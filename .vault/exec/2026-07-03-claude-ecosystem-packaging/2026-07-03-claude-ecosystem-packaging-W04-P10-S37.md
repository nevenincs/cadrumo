---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-17'
body_hash: 'sha256:4dd3e70c36425ad2e1e5ced40b757efbe04e9ba72417c4f8e7701e5f4f17b1c5'
step_id: 'S37'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Have the plugin generator emit the marketplace-served plugin tree so marketplace and plugin cannot drift

## Scope

- `src/aeat/agent/_workspace.py`

## Description

- Add `materialise_marketplace` to the workspace materialiser: one call emits `.claude-plugin/marketplace.json` (name, description, owner object, single `plugins[]` entry sourcing `./plugins/aeat`) AND the plugin tree under that relative source via `materialise_plugin`, so the marketplace manifest and the plugin it serves cannot drift.
- Add the typed frozen `MarketplaceManifest` result (nesting the `PluginManifest`) and wire the lazy package re-exports.
- Commit `d42c26dfbc`.

## Outcome

- The marketplace-served tree is a single generated emission from the one authored harness source.

## Notes

The implementing agent's session was terminated by the account rate limit after writing the implementation; the coordinator verified the WIP (ruff clean, live emission check OK, 10 plugin tests green) and landed it. The design keeps the CLI surface untouched — the marketplace emission is a generator function consumed by the packaging/release lane, not a new `--layout` value (the operator-facing CLI stays plugin|workspace; the marketplace is a release-time artifact).

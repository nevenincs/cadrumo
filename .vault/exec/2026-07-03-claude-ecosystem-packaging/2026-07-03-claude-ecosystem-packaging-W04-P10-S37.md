---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S37'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace claude-ecosystem-packaging with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S37 and 2026-07-03-claude-ecosystem-packaging-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Have the plugin generator emit the marketplace-served plugin tree so marketplace and plugin cannot drift and ## Scope

- `src/aeat/agent/_workspace.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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

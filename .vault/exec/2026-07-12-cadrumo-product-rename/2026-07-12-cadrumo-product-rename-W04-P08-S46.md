---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-17'
body_hash: 'sha256:e8c444feabb826a61d29354f99688674585aaacaad23a54387b80fa53ab72619'
step_id: 'S46'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Update MCP allowlists and recompute tool-name budgets

## Scope

- `src/cadrumo/entrypoints/mcp tests`

## Description

- Hard-cut generated MCP command tools to the `cadrumo_` prefix and the client-visible namespace to `mcp__plugin_cadrumo_cadrumo__`.
- Rename the corpus-search, terminology-search, harness-load, and identity tool authorities without aliases.
- Recompute the 64-character client budget and add stable segment abbreviations for every over-budget live command.
- Retarget tool allowlists, activation, identity, SDK-adaptation, and dispatch tests to canonical names.
- Preserve AEAT names that identify the tax authority, live authority families, registry taxonomy, or official evidence.

## Outcome

Every exposed product tool now has a canonical `cadrumo_` name, and the Claude
plugin prefix is `mcp__plugin_cadrumo_cadrumo__`. The live descriptor set remains
unique and exactly reversible after abbreviation, and every client-visible name
fits the unchanged 64-character ceiling. No former tool-name alias or fallback
is accepted.

## Notes

- The budget gate passed all four uniqueness, reversibility, ceiling, and anti-tautology tests.
- The owned non-server MCP suite passed 76 tests in 60.25 seconds; Ruff and formatting passed.
- The broader serving-gate attempt had two failures in the dirty shared checkout: a missing executable surfaced as `WinError 2`, and a telemetry assertion observed an unlisted tool. `_server.py` belongs to Terra's S43 and was not modified; the owned descriptor, budget, allowlist, and activation tests are green.
- `test_meta_tools.py` carried pre-existing S45 edits. Its synthetic `aeat_x_submit` fixture is not a shipped product name, and S46 neither stages that file nor interprets the fixture as a compatibility alias.
- The plan already contains staged and unstaged peer closures, so S46 does not stage or commit the shared plan checkbox; central orchestration must reconcile it.

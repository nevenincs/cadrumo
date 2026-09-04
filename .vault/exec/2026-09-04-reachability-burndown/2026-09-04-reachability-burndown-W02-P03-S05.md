---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:b84c9464e034679d0283b30884bb3d3817dfcc7e13302962c0dc06d7235d1f42'
step_id: 'S05'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Relocate test-only support into the wheel-excluded test tree and prove the distributed artifact no longer carries it

## Scope

- `src/cadrumo/tests`

## Changes

- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --json` -> `pass`

## Notes

No relocation: this Phase has no in-scope subjects, and that was established against the
tree rather than read off the classification ledger.

Searching the shipped package for test-support-shaped modules outside the wheel-excluded
test tree returns twelve `_support`, `helper` and `factory` modules, none of which the
audit reports -- every one is reachable from a console script and is ordinary production
code whose name merely resembles scaffolding. The only support-shaped modules the audit
does report are four TUI devtools fixture builders: `fixture`, `modelo_fixtures`,
`home_fixtures` and `workbench_fixtures`.

All four sit under the deferred `cadrumo.entrypoints.tui` prefix, so they belong to the
TUI campaign, not this one. They are worth naming for that campaign: fixture builders
shipping inside the distributed wheel is exactly the shape this Phase exists to correct,
and the wheel-excluded test tree is where they would belong once their owner can move
them.

Checking the tree rather than the ledger is the discipline this campaign learned when
attempting a remedy disproved a whole class. Had this Step trusted the ledger's empty
`test-support` set, the four fixture modules would never have been named at all.

---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:4d1364f01fd71d446c086ccdd7f6fb8b088fb8eea3d9f584bcda343e57170310'
step_id: 'S23'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Inventory every exported-but-unimported name by owning area and propose a disposition per area for an owner's ruling

## Scope

- `dev/audit`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync pytest dev/audit/tests/test_reachability_classification.py -m ""` -> `pass`

## Notes

The inventory proposes no blanket disposition, because the reason a name went
unconsumed differs by area and the areas have different owners. Three areas
hold 135 of the 368, so a per-area ruling is tractable where a per-name sweep
would not be.

Two areas carry a documented trap rather than a simple choice. In
`entrypoints/cli` an exported constant may be unconsumed because consuming it
is structurally blocked: wiring `MODELO_CODE_CHOICE_ALL` into the portal filter
it was written for broke the live-subtree demand-loading contract. In
`adapters/persistence` a row type or namespace constant may be the only
declaration of a persisted shape, so removing one changes the schema rather
than the API.

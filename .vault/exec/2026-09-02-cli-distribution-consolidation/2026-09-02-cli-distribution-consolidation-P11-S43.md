---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:a3f30322265a2aa4e59e325d577b86b16036087962f2517c11ca6311486d8147'
step_id: 'S43'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---

# Reduce the recipe surface to the commands the adopted path uses

## Scope

- `justfile`

## Changes

- `M` `justfile`
- `verify:` `just --list` -> `pass`
- `verify:` `just release-readiness` -> `blocked, as documented`

## Notes

`release-collect-evidence` is gone in both host variants. It downloaded evidence rows
from draft releases tagged `evidence-<lane>-<run-id>`, a transport a live gate forbids
every workflow from creating; its own comment asserted the inverse of the current design,
claiming Actions artifacts were retired; it named a companion emitter that does not
exist; and it counted toward a row total the descriptor no longer declares.

Four stale references went with it: the release group's own preamble still named the
retired publication workflow and its environment, the release preview printed that an
orchestrator applies the bump, and two recipes linked to a runbook anchor that never
existed.

No recipe invokes a module or workflow that is absent - checked across the whole file
rather than the release group. The surface stays large at ninety-nine recipes against
the siblings' handful, but the remainder are live developer commands, and cutting those
would be a judgement about what is used rather than a removal of what is broken.

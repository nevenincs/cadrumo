---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:49dd830a371c3ee2fe6ebabb84c3592f530d2b629c42d75e3d3d360deb8dd3fb'
step_id: 'S12'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---
# Remove the harness distribution and its workspace membership

## Scope

- `src/cadrumo_harness`

## Changes

D src/cadrumo-harness/pyproject.toml
M pyproject.toml
M uv.lock

## Notes

Carried by the merge Step: the sub-project's own project file, the workspace table, the
path source pin and the development-group self-reference all had to go in the same
change that moved the package, or the environment would have resolved a distribution
that no longer builds. The lockfile no longer records the distribution at all, and a
frozen sync uninstalls it.

---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-07-17'
body_hash: 'sha256:7b8873f71d4e830d107f95c173d8c758b5e41d47dc7b70fb91f40c8f72e52504'
step_id: 'S20'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# `repo-health-triage` `W02.P06.S20`

Scope: `src/aeat/application/aggregation/_source_mesh.py`.

## Description

- Added explicit protocol ellipses to property and method bodies.

## Outcome

Pyright no longer treats the source-mesh protocol members as empty concrete
methods with missing return paths.

## Notes

No runtime behavior changed.

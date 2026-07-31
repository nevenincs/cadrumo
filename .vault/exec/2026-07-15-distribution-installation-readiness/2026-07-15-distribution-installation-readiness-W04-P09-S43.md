---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-16'
modified: '2026-07-16'
body_hash: 'sha256:485aa79bde4754f1af50113334ab89e79ab31a8aa95b34a50cc5ce0048d7bad5'
step_id: 'S43'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Remove local release upload authority while retaining diagnostic build recipes

## Scope

- `justfile`

## Description

- Remove local PyPI upload recipes and token-driven publication commands.
- Retain diagnostic cohort construction and smoke recipes.
- Leave publication absent until the protected complete-cohort workflow is implemented.

## Outcome

- `just publish` and `just publish-data` no longer exist.
- Exact searches and structural tests confirm there is no local token upload path.

## Notes

- Documentation-site deployment recipes are unrelated and remain intact.
- `.github/workflows/publish.yml` currently validates retained Python candidate bytes
  only; it has no upload authority.

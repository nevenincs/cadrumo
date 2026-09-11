---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:33ae3a3e728dc3088c766f1f3dbcd24edbc9f50e04ca3760cce9967bd241d380'
step_id: 'S29'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Keep documentation under the exact posture-explicit docs manifest authorized by the ADR

## Scope

- `justfile`

## Changes

- `M` `justfile`
- `verify:` `git diff --check -- justfile` -> `pass`

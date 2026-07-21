---
tags:
  - '#exec'
  - '#arch-remediation-registry-format'
date: '2026-07-02'
modified: '2026-07-08'
step_id: 'S06'
related:
  - "[[2026-07-02-arch-remediation-registry-format-plan]]"
---

# Migrate modelo 187 inline revision to the fragmented layout in one atomic commit gated by the equality test and a green registry validator

## Scope

- `src/aeat/_data/registry/aeat/modelos/187`

## Description

- Migrate modelo 187 (2019-y-siguientes) to fragmented; byte-identity proven.

## Outcome

187 fragmented; byte-identical. Commit `55a6de58aa`.

## Notes

Migrated by the coordinator inline (the registry-format agent was rate-limited); a byte-identity migration harness proved the compiled ModeloRevision unchanged. A peer's no-pathspec commit swept the staged batch into `55a6de58aa` (mis-attributed but correct + harness-verified).

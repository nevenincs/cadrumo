---
tags:
  - '#exec'
  - '#arch-remediation-registry-format'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:7c02f9c08fd2f1ac42d2199977709078a4ea9e70d048fd3ec698f282b725cb39'
step_id: 'S08'
related:
  - "[[2026-07-02-arch-remediation-registry-format-plan]]"
---

# Migrate modelo 194 inline revision to the fragmented layout in one atomic commit gated by the equality test and a green registry validator

## Scope

- `src/aeat/_data/registry/aeat/modelos/194`

## Description

- Migrate modelo 194 (2019-y-siguientes) to fragmented; byte-identity proven.

## Outcome

194 fragmented; byte-identical. Commit `55a6de58aa`.

## Notes

Migrated by the coordinator inline (the registry-format agent was rate-limited); a byte-identity migration harness proved the compiled ModeloRevision unchanged. A peer's no-pathspec commit swept the staged batch into `55a6de58aa` (mis-attributed but correct + harness-verified).

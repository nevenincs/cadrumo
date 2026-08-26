---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:8b111ddefc418fee65b409114b6105ff607346fa25e1ac8d83bf1f0a726d3912'
step_id: 'S40'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Sweep every family for synonym-split verbs and record the view-versus-show finding with evidence

## Scope

- `.vault/audit/`

## Changes

- `M` `.vault/audit/2026-08-25-cli-root-verb-homes-audit.md`

## Notes

No code change. The finding was persisted with its evidence and left explicitly
marked as needing a ruling, because the accepted ADR's D2 governs data movement
only and says nothing about read verbs. The operator ruled on it in the following
session and it was executed as S41.

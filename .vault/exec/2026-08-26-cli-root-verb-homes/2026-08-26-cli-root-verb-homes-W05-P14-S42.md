---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:7c678f9360946ff31602ef518bcad439b1e00e6cf85b09831ab911cc744c3709'
step_id: 'S42'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Examine every remaining synonym group against the tree and record the three that are principled

## Scope

- `.vault/audit/`

## Changes

- `M` `.vault/audit/2026-08-25-cli-root-verb-homes-audit.md`

## Notes

No code change. Three synonym groups were examined and all three are principled:
`remove` versus `delete` is membership versus entity, `status` versus `check` is
offline state versus authority validation, and `config auth apoderado check`
refuses by design because the live AEAT read at that boundary is sealed.

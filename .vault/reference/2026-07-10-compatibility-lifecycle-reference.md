---
tags:
  - '#reference'
  - '#compatibility-lifecycle'
date: '2026-07-10'
modified: '2026-09-08'
body_hash: 'sha256:2be336dd891a026e4076e1965e04669c3a7d210c78627ca07d046c6f6947d108'
related:
  - "[[2026-07-09-compatibility-lifecycle-adr]]"
---

# `compatibility-lifecycle` reference: `release-checkpoint flip checklist`

## Summary

The former mechanical flip checklist is withdrawn. It depended on the deleted `COMPATIBILITY_REGIME`, `RELEASED_FORMAT_FLOORS`, persisted-format classification inventory, and synthetic lifecycle gates, all of which were development state embedded in production and had no product consumer.

Release-time durability remains governed by the amended `2026-07-09-compatibility-lifecycle-adr` and `2026-07-08-released-data-durability-adr`: a real schema transition must introduce the reader or migration that consumes the prior released shape and prove restorability through the owning production path. No dormant flip constant, hand-maintained format census, empty fixture corpus, or predeclared upgrade API is retained ahead of that transition.

---
tags:
  - '#research'
  - '#live-pull-verification-sweep'
date: '2026-06-12'
modified: '2026-07-17'
body_hash: 'sha256:a187a06817a49060c2cbc4af6e978cce0807b2ca892a80919c62fc6aa004c6a2'
related:
  - '[[2026-06-12-live-pull-verification-sweep-adr]]'
---

# `live-pull-verification-sweep` research: investigation backing the decision

This research captures the investigation that backed the `live-pull-verification-sweep` ADR.

## Findings

The investigation scoped the residual live-verification acceptance work exposed by the terminology-search closeout: which AEAT-facing surfaces (censo, filed-history, justificante, expedientes, notifications, live-backed calendar) still needed an authenticated read-only proof. It defined the pull-only, per-surface acceptance approach the ADR adopts.

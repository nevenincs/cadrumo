---
tags:
  - '#research'
  - '#calculation-engine-foundations'
date: '2026-06-10'
modified: '2026-07-17'
body_hash: 'sha256:fb1e8490b580e752d790c8b397ef0cae1d1c7b620ffe8a0a368ccb32c945f255'
related:
  - '[[2026-06-10-calculation-engine-foundations-adr]]'
---

# `calculation-engine-foundations` research: investigation backing the decision

This research captures the investigation that backed the `calculation-engine-foundations` ADR.

## Findings

The investigation found the engine's aggregation channels overlapped (one fold-in modelled both as a relation and a previous_filing binding) and that revision selection could be driven by a stored id. It scoped the two foundational decisions the ADR ratifies.

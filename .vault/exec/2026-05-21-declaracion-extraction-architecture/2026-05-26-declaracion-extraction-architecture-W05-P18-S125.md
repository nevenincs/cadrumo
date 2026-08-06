---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-26'
modified: '2026-07-31'
body_hash: 'sha256:c4c5f911c0f39b0055c1df538e65c7592b4418e017345175dad056f38a07a738'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-26-no-synthetic-sede-live-surfaces-research]]'
  - '[[2026-05-26-declaracion-extraction-architecture-W05-P18-S123]]'
---

# W05.P18.S125 - no-synthetic-Sede live-surface research

Persisted the S124 research artifact for the broader no-synthetic-Sede policy
conflict surfaced while closing the declaration-acquisition language.

## Findings

- Existing Modelo 100 Renta WEB Open, Modelo 349 GROI, and Modelo 349 IXVI
  live cross-references currently permit synthetic data on AEAT-hosted
  endpoints.
- Those entries follow accepted live-parity ADRs, so registry/code changes
  should be preceded by an ADR amendment or supersession.
- For declaration extraction, the immediate consequence is already applied:
  live preview/download with synthetic data is no longer an acquisition path.

## Next Gate

`W05.P18.S124` remains open. It should produce the ADR/plan slice that decides
how to supersede the existing live-parity taxonomy and then changes registry,
remote-state guard, and live test behavior.

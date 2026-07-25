---
tags:
  - '#exec'
  - '#post-release-distribution'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S35'
related:
  - "[[2026-07-17-post-release-distribution-plan]]"
---

# DONE 7d20b2d984, concurrent publication is closed rather than only recorded, the marketplace push re-clones and re-applies on a rejected push because concurrency groups are per-repository and cannot serialise across product repos, and refuses after three lost races. GATE, a workflow conformance test pins the retry, the re-clone inside the loop, and the fail-closed exhaustion

## Scope

- `.github/workflows/publish-release.yml`

## Description

- Wrap the marketplace push in a re-clone-and-reapply retry.
- Refuse after three lost races rather than reporting success on an unpublished marketplace.
- Pin the retry, the in-loop re-clone, and the fail-closed exhaustion with a workflow conformance test.

## Outcome

Concurrent publication is closed rather than only recorded. Two products releasing into one shared marketplace can interleave clone and push, making the later push a non-fast-forward.

## Notes

A repository-level concurrency group cannot solve this: groups are scoped per repository, so they cannot serialise across separate product repositories. The retry is safe to repeat because the publish step is a pure function of the marketplace tree and the cohort. This is an expected operating condition under a shared marketplace rather than an edge case, which is why it was worth closing now. Semantic search was degraded for the whole of this work: the code index served roughly a fifth of the tree while reporting itself healthy, so a search miss was worthless as evidence. Discovery was done by direct directory listings, file reads, and targeted pattern search instead.

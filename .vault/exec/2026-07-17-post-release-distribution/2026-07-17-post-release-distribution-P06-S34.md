---
tags:
  - '#exec'
  - '#post-release-distribution'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:db8283c92b81110f54013e67b4c9c9ef164c884163bed6d4d17045c5a7a034e6'
step_id: 'S34'
related:
  - "[[2026-07-17-post-release-distribution-plan]]"
---

# DONE 7d20b2d984, plugin-name collision refuses instead of silently overwriting, index entries carry published_by and a cohort declaring a name another product published is refused, while an unattributed entry stays claimable so the first release adopting it is not deadlocked. GATE, the sibling tree and its attribution both survive a refused takeover

## Scope

- `dev/packaging/marketplace_publish.py`

## Description

- Carry the publishing product on each marketplace index entry.
- Refuse a cohort declaring a plugin name another product published.
- Leave an unattributed entry claimable, and infer the publisher for a single-plugin cohort.

## Outcome

A collision refuses instead of silently overwriting. Ownership was keyed on bare plugin name, so a cohort declaring a sibling's name replaced that sibling's tree and index entry with no warning.

## Notes

This is the same loss the module was written to prevent, reachable by a different route: narrowing the wholesale replacement stopped a release deleting every sibling plugin, and left it able to delete exactly one. An unattributed entry stays claimable deliberately, because refusing it would deadlock the first release that adopts ownership tracking. The shipped marketplace manifest publishes unchanged, since a single-plugin cohort infers its publisher. Semantic search was degraded for the whole of this work: the code index served roughly a fifth of the tree while reporting itself healthy, so a search miss was worthless as evidence. Discovery was done by direct directory listings, file reads, and targeted pattern search instead.

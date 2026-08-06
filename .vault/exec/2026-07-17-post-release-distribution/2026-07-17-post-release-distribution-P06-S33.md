---
tags:
  - '#exec'
  - '#post-release-distribution'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:d37b60abc545785b55a95c2c6e014e1022cf1c428301319a225bd42048a9689b'
step_id: 'S33'
related:
  - "[[2026-07-17-post-release-distribution-plan]]"
---

# DONE 7d20b2d984, marketplace publish is atomic, the whole cohort validates before any mutation so a refusal leaves the tree byte-identical, and the multi-plugin case that was entirely uncovered now has both a refusal test and a success test. GATE, the pre-fix loop leaves a torn tree so the atomicity test discriminates

## Scope

- `dev/packaging/marketplace_publish.py`

## Description

- Split validation from mutation, so the whole cohort validates before anything is written.
- Add a multi-plugin refusal test asserting the marketplace is byte-identical afterwards.
- Add a multi-plugin success test, so the path is proven to work and not merely to fail safely.

## Outcome

A refusal now mutates nothing. Validation previously ran inside the mutation loop, so a two-plugin cohort whose second entry had no tree left the first already replaced and the index unmerged.

## Notes

Every prior test cohort declared exactly one plugin, so this entire class was uncovered while the module's docstring claimed both operations were idempotent. That claim was false on the refusal path and is now corrected. Simulating the pre-fix loop leaves a torn tree, which is what makes the new test discriminating. Semantic search was degraded for the whole of this work: the code index served roughly a fifth of the tree while reporting itself healthy, so a search miss was worthless as evidence. Discovery was done by direct directory listings, file reads, and targeted pattern search instead.

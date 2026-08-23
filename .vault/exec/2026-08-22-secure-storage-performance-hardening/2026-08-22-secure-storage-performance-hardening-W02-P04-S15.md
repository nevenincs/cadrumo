---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:1c09f7ca43e2f27ee2e6a6b34a28ba8783aec189af0831ba2c226fb81509f575'
step_id: 'S15'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# Keep distributed CommandSpec modules import-light by splitting heavyweight handler payload and schema implementations behind owned lazy public targets while retaining all structural declarations in production specs

## Scope

- `src/cadrumo/entrypoints/cli/`

## Description

- Audit every distributed CommandSpec module for heavyweight imports and preserve
  structural declarations as deferred targets.
- Remove eager root payload imports from CLI startup and resolve each payload only in
  its owning root or app execution branch.
- Replace stale scalar command counts with dynamic exact-graph enrollment and verify
  every declared schema and non-bootstrap handler target remains unloaded after graph
  import.

## Outcome

All 364 live root, group, and leaf declarations remain production-authored CommandSpec
nodes. Distributed spec modules import only structural primitives, sibling aggregators,
and lightweight policy declarations. Root payload schemas no longer load during CLI
startup, and the retired facade exports had no production consumer. Thirteen focused
tests and Ruff pass; independent review found no blocking issue.

## Notes

The graph-import test narrowly excludes the package-level root bootstrap handler target
because Python must initialize that package before importing its CommandSpec submodule.
The exception covers only the two root callbacks and is revisited by the following
owned-public-target step. No harness or external-client file was modified.

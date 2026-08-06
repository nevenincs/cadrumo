---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-17'
body_hash: 'sha256:3f023cf4b4ef7c2c66595e2900c12d3dbb99e063e44d215de7343c58ace6a430'
step_id: 'S09'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Move the production package root without leaving an aeat import package

## Scope

- `src/aeat to src/cadrumo package tree`

## Description

- Verified resolved source and target roots remained inside the workspace.
- Relocated the complete dirty `src/aeat` tree into `src/cadrumo` with native PowerShell moves.
- Preserved staged, modified, deleted, tracked, and untracked content while merging the existing identity core.
- Retained both core facade contracts in the relocated `core/__init__.py` without an alias package.

## Outcome

Moved the entire source tree to `src/cadrumo`; `src/aeat` no longer exists. The move carried 218 overlapping source changes recorded by the ownership ledger, all mechanically relocated tests, bundled data, and ignored runtime cache files. The existing `product_identity.py` remained byte-preserved. The sole source collision, `core/__init__.py`, was resolved by retaining the full relocated core facade and adding the four canonical identity re-exports.

Twenty-four ignored bytecode filename collisions were preserved with `.relocated-aeat` suffixes; they are not source or staged artifacts. No imports, dynamic strings, registry targets, or test semantics were rewritten in this Step.

## Notes

- The first merge pass moved all source content but PowerShell reported errors removing some newly emptied directories; a second bottom-up non-recursive cleanup removed them. One duplicate bytecode collision required a second unique suffix. No source file was lost.

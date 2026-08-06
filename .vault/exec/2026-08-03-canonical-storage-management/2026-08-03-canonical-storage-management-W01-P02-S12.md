---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:c78b1ce24b80d3cb3f209407ed8e7a0150397cb2e5734fa1a160b3df8e93707d'
step_id: 'S12'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Rewrite ensure_storage_tree to materialise the taxonomy-derived member set and delete the path-suffix file inference, gated by the existing file-valued-setting test asserting the parent is created and the leaf is not

## Scope

- `src/cadrumo/core/config.py`

## Description

- Rewrite `ensure_storage_tree` to materialise the taxonomy-derived member set, deleting the `field_name.endswith("_path")` suffix inference.

## Outcome

Landed in commit `d05e564cbf` ("build the state tree on invocation, from the taxonomy's own declaration"). Gated by the existing file-valued-setting test in `test_ensure_storage_tree.py`.

## Notes

This commit also wires `ensure_storage_tree` into the CLI root callback (materialisation on invocation) — broader scope than S12's literal text, not incorrect but folded into the same commit rather than a separate change.

---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:42d3931578974c1b905a7faa7644abf475ed4c56b53168510825671ccf599334'
step_id: 'S53'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Canonicalize duplicated LLM secure-runtime fixtures at their narrowest common owner

## Scope

- `src/cadrumo/llm/conftest.py`
- `src/cadrumo/adapters/outbound/llm/conftest.py`

## Description

- Move the duplicated secure-runtime fixtures into one canonical test-support module.
- Keep both LLM conftests as direct-import pytest visibility boundaries.
- Preserve exact function scope, autouse reach, encrypted-runtime lifecycle, and teardown.
- Refresh the executable import contract and fixture ownership manifest for the selected owner.

## Outcome

Both LLM trees now discover the same two canonical fixture objects, while unrelated source-tree tests do not receive the autouse backend. The fixture census dropped from 709 to 708 declarations, the two obsolete conftest owners disappeared, and the manifest names the canonical module.

## Notes

The first implementation lifted the autouse fixture to `src/cadrumo/conftest.py` and was rejected because that widened setup to every source-tree test. The corrected boundary uses direct imports without wrappers or aliases. A second review caught stale import-linter and ownership-manifest evidence; both were corrected. Representative tests passed 10 cases, setup and teardown traces passed in both LLM trees, a non-LLM negative control passed, Ruff passed, and the exact LLM import contract reported one kept and zero broken contracts.

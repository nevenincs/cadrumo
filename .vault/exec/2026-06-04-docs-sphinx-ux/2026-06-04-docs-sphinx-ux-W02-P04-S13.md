---
tags:
  - '#exec'
  - '#docs-sphinx-ux'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:6bd47d101c0bc2d225c55bd812b3f87a868608d557aa01be4b7aaab926b83b0d'
step_id: 'S13'
related:
  - "[[2026-06-04-docs-sphinx-ux-plan]]"
---

# update CLI reference conformance expectations

## Scope

- `src/aeat/entrypoints/cli/test_doc_reference_conformance.py`

## Description

Verified the live conformance gate is
`src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py` (the scoped
path never existed post-rename). Ran the gate with
`uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py -m integration -q`
and confirmed 69 tests passed (13 test functions, several parametrized), covering
documented-command conformance, live introspection parity, and inline-span/fence
scanning against the shipped docs.

## Outcome

Step closed as already-satisfied. No new commit required; this record documents the
verification only. The stale scope path is not rewritten on this step per adjudication;
the real implementation site is
`src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py`.

## Notes

Ran the gate at HEAD (commit `d029acb9968f`); 69 passed, 0 failed.

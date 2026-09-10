---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:d6fb70810b4520e7e4769f66b9ae2dc8e748b677aadb144770b97ddd45078826'
step_id: 'S09'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

# [M | opus-medium] Add the predecessor key to the edition schema. An edition is delta-authored only when it declares one; the loader never infers it from absent rows. Proof: an edition without the key loads as a full-copy edition unchanged.

## Scope

- `src/cadrumo/domain/calculations/registry`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/schema.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_revision_predecessor_declaration.py`
- `verify:` `uv run --no-sync aeat app registry verify` -> `pass`

- `verify:` `pytest test_revision_predecessor_declaration.py` -> `pass` (10)
- `verify:` all 128 revisions dumped before and after -> byte-identical

## Notes

The executing agent could not launch the reviewer persona; the orchestrating session reviewed the diff against the ADR's format section instead.

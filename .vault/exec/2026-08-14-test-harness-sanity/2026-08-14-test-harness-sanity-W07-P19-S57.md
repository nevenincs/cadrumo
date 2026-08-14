---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:4b9eebcf2ecdf55c2a090c41c2a1058762f3e60f1eb55232d156b0eb4514e6c0'
step_id: 'S57'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Canonicalize isolated profile-storage fixtures used by wizard and CLI profile tests

## Scope

- `src/cadrumo/application/wizard/tests`
- `src/cadrumo/entrypoints/cli/tests`

## Description

- Adjudicate the isolated profile-storage body family across wizard and CLI tests.
- Replace nine backend and three source fixture definitions with two direct-object support owners.
- Preserve function scope, autouse behavior, real storage-root teardown, and module-local visibility.
- Retain three lookalike owners whose names, constraints, or storage semantics differ.

## Outcome

Twelve CLI consumers now register one of two canonical fixture objects through direct imports and explicit module exports. No broad CLI conftest, alias, wrapper, bridge, or lint suppression was introduced; the wizard and class-level divergent lifecycles remain local.

## Notes

Static AST registration proofs, exact census adjudication, Ruff, diff integrity, peer-hunk preservation, and independent review passed. Focused collection is currently blocked before these modules import because concurrent registry work removed `_clear_fingerprint_cache` while its loader import remains; no fixture-specific behavior claim is made. Four consumer files carry adjacent peer changes, so delivery remains pending safe hunk isolation.

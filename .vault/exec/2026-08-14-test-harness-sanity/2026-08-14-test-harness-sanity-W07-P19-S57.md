---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:1ca76f5928e552c8b0befd490a8c18f6f816afa1a9b230322286891431a906d6'
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

Static AST registration proofs, exact census adjudication, Ruff, diff integrity,
peer-hunk preservation, and independent review passed. Collection reached 67 tests;
five modules are blocked by the peer removal of `profile_create_storage_span`, while
backend behavior also encounters the peer removal of `config profile create`. A
source-fixture behavior control passed. No compatibility bridge was introduced.

The resulting support and consumer changes were swept into peer commit `7c062ed17e`
while the shared tree was active. History was not rewritten; this record attributes the
fixture result independently of that commit subject.

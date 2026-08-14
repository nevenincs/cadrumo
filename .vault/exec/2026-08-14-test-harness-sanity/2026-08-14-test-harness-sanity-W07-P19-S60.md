---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:c0b774b5284cb49436a7a156648694033123d0b6e178abbe1a5bc02f6511e124'
step_id: 'S60'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Canonicalize schema-loader fixtures while preserving proven scope

## Scope

- `src/cadrumo/domain/user_profile/tests`

## Description

- Replace seven identical schema-loader fixture bodies with two canonical scope-preserving providers.
- Import exactly one provider object into each former owner module according to its existing lifecycle.
- Keep the effective fixture name `schema` while avoiding competing conftest visibility or wrapper fixtures.
- Refresh codebase-wide fixture ownership evidence against the current shared worktree.

## Outcome

Four module-scoped consumers and three function-scoped consumers now share their matching canonical provider. All 50 affected tests pass, fixture discovery resolves to the support owner, and setup-plan evidence preserves per-module versus per-test cadence.

## Notes

Ruff, collection, focused execution, fixture-object identity, cadence probes, diff integrity, and independent review passed. Semantic RAG was unavailable in the local service environment, so the implementation used the accepted ADR, campaign research, ownership census, and exact source fallback.

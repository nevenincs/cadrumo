---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:e414405efdddd87e3c0c187f8e0d3af512912ed86fff9b5cc1ca2adc133dfd9a'
step_id: 'S69'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Migrate local outbound-storage provider failures to typed no-recovery outcomes

## Scope

- `src/cadrumo/adapters/outbound/storage/_errors.py`
- `src/cadrumo/adapters/outbound/storage/_local.py`
- `src/cadrumo/adapters/outbound/storage/tests`

## Description

- Equip storage-corruption failures with the shared terminal-precondition transport while preserving `CoreError` semantics.
- Project every local-provider permission, path-length, conflict, not-found, integrity, and sidecar-corruption branch through the canonical no-action helper.
- Reserve provider/input validation branches for S128.
- Prove the complete production raise-site census and exact machine contract for every distinct failure family.

## Outcome

All 24 in-scope local-provider raise sites now carry typed terminal facts. Permission, path, integrity, corruption, and destructive-operation failures resolve to `SAFETY`; local commit conflict and absence cases use the explicitly adjudicated operator-decision outcome. No caller-owned recovery action was invented.

The focused local-provider module passes 69 tests. Its totality table matches the production verdict multiset exactly, while real filesystem tests exercise representative branches. Scoped Ruff and diff checks pass. Independent review confirmed zero untyped S69 sites and no direct verdict or evidence construction.

## Notes

- The three namespace/key/content-hash validation raises remain intentionally open under S128.
- VaultSpec RAG identified the shared no-action helper as the canonical home; exact scanning confirmed this scope only delegates to it.

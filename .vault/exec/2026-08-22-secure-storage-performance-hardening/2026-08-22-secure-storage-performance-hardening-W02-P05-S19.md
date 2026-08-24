---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:bf6f173d1cc7a604580e772e5b7784328e813495aeb139d12358cd51662cc842'
step_id: 'S19'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# Move heavy workflow contracts into cohesive sibling modules loaded only by owning commands

## Scope

- `src/cadrumo/application/workflow/`

## Description

- Atomically replace the broad workflow model monolith with cohesive state and run
  contract owners plus a shared period-identity leaf.
- Repoint the lazy facade, internal consumers, tests, and architecture ledger to the
  canonical owners and delete the old module without a bridge.
- Prove public object identity, state persistence, run persistence, and declaration
  helper behavior through focused tests.

## Outcome

State-only consumers no longer construct run/deadline/browser contracts, and run-only
consumers no longer construct encrypted state/profile contracts. The retired model
module has no production or architecture-ledger reference. Ruff passes and 34 focused
tests pass; independent review approved the split.

## Notes

The import-linter ledger test still reports four pre-existing missing TUI-launcher rows
outside this step. No harness or external-client file was modified.

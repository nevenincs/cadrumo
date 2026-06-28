---
tags: ['#exec', '#live-pull-verification-sweep']
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S05'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
---

# W01.P02.S05 - Remote-operation registry policy audit

Scope: prove only read-shaped AEAT remote operations are allowed and write-shaped operations fail closed.

## Description

- Inspect the remote-operation guard policy surface.
- Run the registry remote-state guard tests.
- Record the current policy shape for later live backend and CLI rows.

## Outcome

The remote-operation guard classifies public read, authenticated read, simulator, workbook, and prohibited write surfaces. It rejects write-class HTTP methods unless they are explicitly declared read POST paths on authenticated read surfaces. It rejects forbidden AEAT write tokens in URLs, paths, actions, and declared operations. Browser actions must match explicit read-only allow-list patterns.

The guard tests passed as part of the focused 52-test gate and cover allowed reads, forbidden methods, forbidden write-action tokens, host allow-lists, read POST exceptions, and typed diagnostics.

## Verification

- `rg -n "RemoteOperation|RemoteStateGuardPolicy|assert_remote_operation_allowed|evaluate_remote_operation|submit" src/aeat/domain/calculations/registry/_remote_state_guard.py src/aeat/domain/calculations/registry/tests/test_remote_state_guard.py` confirmed the policy and tests.
- `src/aeat/domain/calculations/registry/tests/test_remote_state_guard.py` was included in the combined focused gate with the central access-gate and CLI safety tests.
- The combined focused gate passed with 52 selected tests.

## Notes

This is a registry-policy proof only. Later backend and CLI rows still need to show each concrete surface calls the guard or is otherwise structurally unable to mutate AEAT state.

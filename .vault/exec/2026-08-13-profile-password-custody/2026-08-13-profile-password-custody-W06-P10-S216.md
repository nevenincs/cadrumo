---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:d0e4eeb60e45e7ac22d7cbd081680bdd15bd215f792a01d70b05332161420a88'
step_id: 'S216'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Migrate all remaining direct registration callers and their shared test provisioning doors to supply and verify recovery instead of constructing password-only profiles

## Scope

- `src/cadrumo/tests/ and src/cadrumo-harness/src/cadrumo_harness/`

## Description

- Inventory every direct registration call across the application tree, CLI/TUI tests, storage tests, shared test support, and the harness.
- Supply each ordinary caller with a real handoff that returns the minted enrollment mnemonic, retaining words only where the test needs them.
- Preserve the deliberate missing, mismatched, and raising handoff controls at the application recovery boundary.
- Recursively scan executable modules and embedded child-interpreter source for missing or `None` recovery handoffs.
- Collect all migrated test modules and exercise representative application, storage, CLI, and harness lanes.

## Outcome

Every ordinary `register_profile_with_credentials` caller visible in the live tree now supplies exact recovery proof. The recursive inventory found 136 direct executable-tree calls plus an embedded child-interpreter call; the sole missing handoff is the intentional TypeError control proving that the application parameter is mandatory. No explicit `None`, conditional-`None`, or mnemonic-free lambda handoff remains.

The migrated test corpus collected successfully. A representative eighty-eight-test application/storage/CLI/harness run produced eighty-four passes: two failures are stale optional-recovery assertions assigned to S217, and two are unrelated concurrent capability-output expectations. The embedded-source regression test passes independently. Scoped Ruff is clean across every direct-caller module, and formal re-review reports no remaining CRITICAL, HIGH, or MEDIUM findings.

## Notes

The broad scoped type check reports existing diagnostics in test-only lazy facade annotations and unrelated concurrent test work; its only recovery diagnostics are the deliberate missing-argument and raising-callback negative controls. Comprehensive behavioral reauthoring of tests that assert recovery absence remains S217 rather than being hidden inside this mechanical caller migration. Formal review found one call hidden inside an embedded child-interpreter program that the first AST sweep could not see; the recursive scan and exact integration gate now cover that lane.

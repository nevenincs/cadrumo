---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:e8901bff729cac1f86d6c60be7fcbbf0b7abbfd7038ad5df09962f9c6719bd8d'
step_id: 'S261'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# Compose the canonical profile-custody port in test capsule, documentation sequence, and harness profile fixtures so recovery enrollment uses the production owner without a parallel implementation, then rerun golden and harness proofs

## Scope

- `src/cadrumo/tests/profile_capsule.py and dev/docs/sequences/_runner.py and src/cadrumo-harness/src/cadrumo_harness/mcp/tests/`

## Description

Trace the failed fresh-host recovery enrollment through semantic discovery and exact callers, then bind the existing production custody and login-session adapters through the single public test composition helper at the documentation-sequence and harness host boundaries.

Prove the six S233 custody failures, the sequence runner checkpoint, both affected harness modules, Ruff, ty, and formal review without adding an adapter, protocol, low-level import, or alternate storage route.

## Outcome

Documentation sequences now enter `composed_profile_persistence_ports` after their isolated environment and storage root are established and before the deterministic capsule is published. Harness delivery and warm-runtime fixtures enter the same public composition boundary before calling the canonical credential-registration door. Recovery enrollment, mnemonic possession verification, encrypted profile access, login-session cleanup, and restart behavior therefore exercise the production owners.

The exact six S233 custody failures pass: 6 passed in 130.22 seconds. Both affected harness modules reach 27 passed with one unrelated pre-existing warm no-profile failure. The sequence runner reaches 30 passed with three unrelated derived failures: two stale profile-create frames lack the now-required secret channel, and one test imports the retired provisioning probe. The all-goldens checkpoint advanced beyond the original unbound-port failure and was bounded after ten minutes without output. Ruff and ty pass on all three changed Python modules. Formal review approved with no findings.

## Notes

Semantic discovery found the prior architectural decision that collapsed profile custody into the user-profile owner and forbids a second adapter route. Exact caller search confirmed `composed_profile_persistence_ports` as the existing fresh-interpreter host composition seam. No change to `profile_capsule.py` was required: its recovery helper already calls the canonical application enrollment door; the defect was that non-pytest hosts had not composed that door.

Concurrent provenance: during proof, peer-owned custody-port work temporarily added `ProfileCustodyCapsuleLabelPort` without its facade export, blocking sequence startup. S261 did not touch or revert those files; after the peer published the export, the proof resumed. Remaining sequence and warm no-profile failures are inventoried for their existing derived owners and are not custody-composition regressions.

---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:e95deb3965d7656c2f947961ead2754d8d81e0fc261d4bb95161a7b9c129bae0'
step_id: 'S76'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh unblock capsule-backed coverage in the outbound authority adapter's test package, whose autouse fixture writes the retired bucket manifest so capsule discovery refuses that root outright, leaving no test in the package able to seed a current capsule and the degradation path of the identity-provider session reader with no coverage at all, and sequence it behind the manifest ownership ruling since whoever rules that will be holding this fixture

## Scope

- `src/cadrumo/adapters/outbound/aeat/auth/tests/`

## Description

## Outcome

The row's cause clause was stale and is corrected: the outbound auth test package's autouse fixture writes NO retired manifest at HEAD — the chain is the canonical capsule door (`isolated_runtime_profile` → `publish_test_profile_capsule`). The real blocker was the UUID harness: every module-level `_BUCKET_ID` in the package was a readable string, which `UUID(str(profile_id))` refused once the harness went UUID-constrained (commit `58cd742301`). Swept to canonical UUIDv4 ids (commit `dadca09566`): `_authenticator_support.py`, the two lifecycle f-string ids, the diagnostics/contract/persistence/roundtrip modules and the per-case resume id. Collection is clean and 49 tests that previously errored at setup now run.

## Notes

Routed finding: the newly-runnable tests expose the next pre-existing layer — `ProfileCustodyTransactionConflictError: profile label is already bound to a committed capsule` across the parametrised shared-contract module (the function-scoped runtime fixture with a fixed bucket id collides across cases in one process). That layer belongs to the runtime-fixture owners (`adapters/persistence/tests/runtime_profile_fixture.py`), not this row. Also repaired: this session's earlier fixture UUIDs carried malformed 10-hex tails; corrected to canonical 12-hex length in the same sweep.

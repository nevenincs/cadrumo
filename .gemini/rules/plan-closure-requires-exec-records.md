---
name: plan-closure-requires-exec-records
trigger: always_on
---

# Plan closure requires exec records

## Rule

A plan step must not be marked complete unless a matching exec record exists or the close audit explicitly records why the step is only a deferred carry-forward.

## Why

The `2026-06-11-ledger-hardening-close-audit` found C5 steps already checked without execution records and C4 implementation completed while its plan still showed zero progress. That made the handover harder to trust and hid the actual remaining work. Step checkboxes are the operator-facing truth only when backed by execution evidence.

## How

- **Good:** create one `.vault/exec` record per completed step before or alongside marking the step checked, then rebuild the feature index and run feature-scoped Vault checks.
- **Good:** leave a step unchecked when it is intentionally deferred, and name the follow-up campaign or blocker in the close audit.
- **Bad:** marking a plan step checked based only on code inspection, or claiming a campaign complete while `vault plan status` reports missing exec records.
---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:64d4244e3eac256eb49fa454a8e2aed0152b5cf96ab7c931022c58cd20e0dcfd'
step_id: 'S121'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Migrate Google API transport failures to typed external-system safety outcomes

## Scope

- `src/cadrumo/adapters/outbound/google/_api.py`
- `src/cadrumo/adapters/outbound/storage/_errors.py`
- `src/cadrumo/adapters/outbound/google/tests/test_api.py`

## Description

Migrated Google API transport, permission, quota, unavailable-response, and not-found failures to constructor-carried typed terminal verdicts.

## Outcome

- Network, unavailable, permission, and quota failures declare safety no-recovery outcomes.
- Remote not-found declares operator-decision because caller-owned creation cannot be inferred at the API boundary.
- `OutboundStorageError` uses the standard typed terminal-verdict carrier without a runtime application dependency.
- Tests assert one exact evidence record, evidence and condition identities, provenance, complete branch facts, no action or bindings, conditionality, and outcome for every branch and non-mapping response variant.
- Verification: Google API plus outbound-storage suites — 221 passed; focused ruff and diff checks — clean.
- Independent review: PASS.

## Notes

The shared error-transport change is a prerequisite contribution to the still-open outbound-storage migration row; it does not close that broader row.

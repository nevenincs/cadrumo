---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:34d5ca33fa6344cfcd34179eacd405dcffaa492ec94302686f77f12ba8c1323c'
step_id: 'S68'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Migrate Google profile, OAuth, and impersonation refusals to typed outcomes

## Scope

- `src/cadrumo/adapters/outbound/google/_errors.py`
- `src/cadrumo/adapters/outbound/google/_active_profile.py`
- `src/cadrumo/adapters/outbound/google/_oauth_flow.py`
- `src/cadrumo/adapters/outbound/google/_impersonation.py`
- `src/cadrumo/adapters/outbound/google/tests`

## Description

- Add standard terminal-precondition transport to Google authentication failures.
- Attach canonical no-action verdicts to all active-profile, OAuth, and impersonation refusal carriers.
- Classify insecure modes, missing dependencies/configuration/scopes/identity, token verification, browser/network/bind, ADC, and IAM failures as safety outcomes.
- Classify selectable profile and unavailable live record-session authority as operator decisions.
- Preserve capsule integrity corruption without downgrading it to an authentication refusal.
- Add a mutation-sensitive 20-site totality table and exact runtime contracts.

## Outcome

All 20 Google-auth refusal sites now carry canonical typed terminal facts with no direct verdict/evidence construction. A committed pointer whose custody-backed record session is unavailable resolves to `google.auth.profile_record_session.available` with application-state evidence and an operator-decision outcome. A live capsule with zero current rows continues to raise `ProfileRecordIntegrityError` unchanged.

The full focused auth selection passes 87 tests; focused root verification passes 22 tests and independent review passes 52 owned cases. Scoped Ruff and diff checks pass. Independent review confirmed the 20-site condition, fact-expression, provenance, and outcome census remains exact.

## Notes

- Pydantic configuration-only `ValueError` sites are outside this operator-refusal migration.
- VaultSpec RAG located the canonical application no-action authority and confirmed no Google-auth action-builder redeclaration.

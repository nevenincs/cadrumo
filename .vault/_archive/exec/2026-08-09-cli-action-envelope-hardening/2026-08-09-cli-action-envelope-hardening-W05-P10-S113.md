---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:86c0a2e0be4f77e8f2ca54e73890bc16028aa912f3428d9ce54a93365b15c681'
step_id: 'S113'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Migrate domain-bucket recovery producers to typed conditions and canonical actions

## Scope

- `src/cadrumo/domain/buckets/_errors.py`
- `src/cadrumo/application/bucket_maintenance/tests/test_service_assess_deletion.py`

## Description

Added the standard terminal-precondition verdict carrier to `BucketDeleteRefusedError` so application-owned bucket refusals preserve typed evidence across the domain error boundary.

## Outcome

- Verdict transport introduces no runtime domain-to-application dependency.
- Every bucket refusal test exercises the attachment.
- Verification: combined bucket application/domain suites — 61 passed; focused ruff — clean.
- Independent review: PASS.

## Notes

This supersedes the earlier taxonomy-only observation now that the application service has a real typed verdict to transport.

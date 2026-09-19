---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:cecb554b8f10eb807d57b51963f8959d2f45c100a653b7a1bbcda3930261f640'
step_id: 'S107'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Migrate bucket-maintenance recovery producers to typed conditions and canonical actions

## Scope

- `src/cadrumo/application/bucket_maintenance/_service.py`
- `src/cadrumo/domain/buckets/_errors.py`
- `src/cadrumo/application/bucket_maintenance/tests/test_service_assess_deletion.py`

## Description

Migrated every bucket-deletion refusal to typed failed-condition evidence with an explicit safety no-recovery outcome and registered message identity.

## Outcome

- All seven refusal sites route through one typed helper and cover four closed condition families.
- Tests exercise every distinct family, both retention fact variants, exact evidence, no action, not-applicable conditionality, and safety outcome.
- Verification: combined bucket application/domain suites — 61 passed; focused ruff — clean.
- Independent review: PASS.

## Notes

The former sandbox scope was retired before this execution and was removed from the plan row rather than recreated.

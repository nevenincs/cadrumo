---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:7c4c9d8b3b741075efead5de9469a0abf0e2abb206a88c8839b7e2a05bd005d5'
step_id: 'S57'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Retire recovery-authority comments from the second adapter registry shard and prove its 63 tuple taxonomy remains canonical, retaining historical recovery only in the S50 ledger where 16 migration_required rows are exclusively owned by later producer steps and 2 rows are retired_or_unreachable

## Scope

- `src/cadrumo/core/errors/registry/_adapters_part2.py`

## Description

- Ground the shard against the accepted action-envelope decision, the S50 rehoming join, and semantic plus exact source discovery.
- Capture a comment-insensitive tuple AST baseline and enumerate every comment-based authority claim.
- Remove exactly the three stale recovery/remediation/retry comment blocks while preserving tuple order, fields, and values.
- Replace the stale S57 migration action through guarded Vault CLI with the taxonomy-boundary proof.

## Outcome

- All 63 `ErrorCode` calls preserve exactly `code`, `category`, `message_key`, `retryable`, and `runbook_id`. Pre- and post-edit tuple AST hash is `54b26fd7a741e320b77960404d1078312956a57e4877b2b99914046083f1363b`; post-edit comment count is zero and the production import reports 63 rows.
- The immutable `adapters_part2` partition is 18 rows: 16 `migration_required` and 2 `retired_or_unreachable`. Its 60 current fingerprints are exclusively assigned to S68 (19), S69 (17), S70 (16), S89 (4), S94 (2), S101 (1), and S115 (1), never S50 or S57.
- Direct rehoming validation passed with `E_REHOMING_VALIDATED:238`.
- Core registry tests passed 16 tests; live CLI registry-contract tests passed 30 tests; the complete relocated rehoming lane passed 74 tests.
- Ruff, format, and BasedPyright passed for the scoped shard. No ledger artifact was changed.

## Notes

- The source patch deletes only comment-based authority. No tuple, recovery disposition, canonical producer, locale data, or runtime rendering was added or changed.
- S57 remains open for independent review. No step closure was performed.

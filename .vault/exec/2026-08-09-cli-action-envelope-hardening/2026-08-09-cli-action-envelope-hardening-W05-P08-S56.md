---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:ee51014d47ee569d6ef1201037ce862c23f14de40a3db4f58619285ec91f3e57'
step_id: 'S56'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Retire recovery-authority comments from the first adapter registry shard and prove its 59 tuple taxonomy remains canonical, retaining historical recovery only in the S50 ledger where eight migration_required rows are exclusively owned by later producer steps

## Scope

- `src/cadrumo/core/errors/registry/_adapters_part1.py`

## Description

- Ground the shard against the accepted action-envelope decision, the S50 rehoming join, and fresh semantic and targeted code search.
- Capture a comment-insensitive AST tuple baseline before editing.
- Remove exactly two stale recovery-authority comment blocks using the scoped patch; preserve every tuple, field, order, and surrounding locator.
- Replace the stale S56 migration action through the guarded Vault CLI with the comment-authority retirement and taxonomy-proof boundary.

## Outcome

- The pre- and post-edit `_DECLARED_ERROR_CODES` AST hashes are identical: `6cc73a5080da633cb3a55d32b8e7b739865dd5863239bb1e984957cc9860cc11`. All 59 `ErrorCode` calls retain exactly `code`, `category`, `message_key`, `retryable`, and `runbook_id`.
- The two removed comment blocks contained all six stale authority-comment lines. The post-edit authority-comment scan returned zero matches, and the production import returned 59 rows.
- The immutable `adapters_part1` partition is exactly eight `migration_required` rows. Its 58 current fingerprints are exclusively owned by S58 (9), S70 (47), and S101 (2), with no S50 or S56 ownership and no retired row.
- The direct relocated validator passed with `E_REHOMING_VALIDATED:238`. The single read-only replay returned `E_REHOMING_MIGRATION_CHECK_CONTENT`; no TOML write or external-locator investigation was performed.
- Core registry tests passed 16 tests; live CLI registry-contract tests passed 30 tests; the complete relocated rehoming lane passed 74 tests.
- Ruff, format, and BasedPyright passed for the single shard.

## Notes

- The source patch is limited to stale comment deletion; tuple semantics and registry shape are independently hash-proven unchanged.
- S56 is execution-ready but remains open for independent review. No step closure was performed.

---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:56b2db5e0f00d909238000087a877bf1d421980351d79eaefc7d682ba3896d65'
step_id: 'S360'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---
# FU-S99-A IvaWalletBalanceReport total_balance includes expired lots

## Scope

- `closed by 2dfc2fd75: wallet balance now reports total_balance as gross remaining`
- `active_balance for non-expired ACTIVE/EXPIRY_REVIEW_DUE lots`
- `expired_balance for EXPIRED_REVIEW_REQUIRED lots`
- `and next_expiry_year only from active lots`
- `CLI JSON/text payloads and locale help expose the split`
- `verified by 6 inspector tests`
- `2 seed anti-tautology tests`
- `94 schema-conformance tests`
- `and ruff`
- `ty remains blocked by unrelated missing stubs directory in the shared tree`
- `src/aeat/domain/iva_compensation/_balance.py src/aeat/entrypoints/cli/_modelo_iva_wallet_cli.py src/aeat/entrypoints/cli/_modelo_payloads.py src/aeat/entrypoints/cli/tests/ src/aeat/locales/`

## Description

Reconciled the retained historical execution evidence for this Step. The related reconciliation audit names commit `2dfc2fd75e` as the direct evidence.

No production sources changed.

## Outcome

Restores one-Step/one-record traceability for this checked Step without rewriting historical implementation.

## Notes

The related reconciliation audit names the exact historical evidence. This documentation-only record makes no new production-behavior claim.

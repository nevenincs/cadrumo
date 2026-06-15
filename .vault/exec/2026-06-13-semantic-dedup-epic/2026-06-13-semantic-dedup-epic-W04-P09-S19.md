---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-13'
modified: '2026-06-15'
step_id: 'S19'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---




# Consolidate the duplicate _require_transaction guard in _review_projection onto the canonical in _actions_common

## Scope

- `src/aeat/application/ledger/_review_projection.py`

## Description

- Keep the canonical `_require_transaction` in `application/ledger/_actions_common.py`.
- Remove the byte-identical copy from `_review_projection.py` and import the
  canonical from `_actions_common`; ruff pruned the now-unused
  `TX_BUCKET_NAMESPACE` / `TransactionNotFoundError` imports.

## Outcome

Two identical application-ledger guards collapsed to one; the single call site is
unchanged. The shared function is confirmed identity-equal across modules; 5
review tests pass, ruff + collect-only clean. Landed as commit `e62799969`.

## Notes

The domain-layer `domain/transactions/_service._require_transaction` (no
application namespace context) is a distinct error shape and stays separate —
application cannot be imported from domain.

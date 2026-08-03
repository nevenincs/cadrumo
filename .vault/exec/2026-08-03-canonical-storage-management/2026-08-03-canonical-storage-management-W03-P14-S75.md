---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:56541b4d2bd46bbb63f7dd59b122825d64c3d60fc2098899387823a7c2e014d1'
step_id: 'S75'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Add storage_overrides reading the field and subpath from STORAGE_TAXONOMY so a fixture can no longer disagree with the declaration, and converge the four tier-two isolation fixtures onto it, correcting isolated_cli_runtime_profile's drifted pin of the transactions category to a literal txs directory

## Scope

- `src/cadrumo/tests/secure_sql.py`

## Description

- Add `storage_overrides(anchor, *categories)` in `secure_sql.py`, reading the field and subpath from `STORAGE_TAXONOMY` so a fixture cannot disagree with the declaration.
- Converge the four tier-two isolation fixtures (`isolated_profile_storage_root`, `isolated_runtime_profile`, `isolated_two_bucket_runtime`, `isolated_cli_runtime_profile`) onto it.
- Correct `isolated_cli_runtime_profile`'s drifted pin of the transactions category (literal `txs` vs. the declared `financial/transactions`).

## Outcome

Landed in commit `0f1317c13c`. This is the first tranche of ADR R15's roughly-ten tier-two fixture-internal sites; the remainder is tracked separately (S76).

## Notes

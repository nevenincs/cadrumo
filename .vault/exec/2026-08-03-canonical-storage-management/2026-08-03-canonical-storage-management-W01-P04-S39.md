---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:76279a3c97eb8bc1131d8840f69f73b9660c8afdffa48515278f98c6f60949fd'
step_id: 'S39'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Rewrite the wallet diagnostic dump prune to delegate the survivor decision to the shared selector, gated by the existing wallet diagnostic prune tests

## Scope

- `src/cadrumo/adapters/outbound/aeat/sede/_iva_compensation_wallet.py`

## Description

- Rewrite the wallet diagnostic dump prune to delegate to `select_filesystem_retention_survivors`.

## Outcome

Landed in commit `095bdc4ca2`.

## Notes

Same premature-checkbox / broken-HEAD history as S37; see that record.

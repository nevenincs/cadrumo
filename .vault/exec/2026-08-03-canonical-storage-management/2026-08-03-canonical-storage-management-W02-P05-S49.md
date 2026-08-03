---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:70e3c4f8597bcb444d1b699f45381ae622267f2b936d73b3cd05809f106f9b36'
step_id: 'S49'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Declare the wallet diagnostic dump directory as an operator-directed-output escape, gated by a test asserting the role and that the feature stays off when the field is unset

## Scope

- `src/cadrumo/adapters/outbound/aeat/sede/_iva_compensation_wallet.py`

## Description

- Declare `cadrumo_wallet_diagnostic_dump_dir` in `EXTERNAL_PATH_SETTINGS_FIELDS` under the new `ExternalPathRole.OPERATOR_DIRECTED_OUTPUT` role, ADR R17's fifth role, added because none of the original four fit an operator-named destination for application-written output.

## Outcome

Landed in commit `3ee34dc721`.

## Notes

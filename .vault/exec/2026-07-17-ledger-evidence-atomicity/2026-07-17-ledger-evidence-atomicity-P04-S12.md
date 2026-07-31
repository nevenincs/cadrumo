---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:f541fbcac8a86b1c1d0b0917fca9462ac70688d6690eedb7787eab4c36baabbb'
step_id: 'S12'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
---

# Migrate the ledger evidence and audit family help and risk metadata to the accepted grammar

## Scope

- `src/cadrumo/application/operator_surface/_help.py`

## Description

- Remove the orphaned `modelo.audit.replay` command-risk declaration from `_risk_table.py`.
- Remove the never-emitted `MODELO_AUDIT_REPLAYED` (`modelo.audit.replayed`) member from the `BucketEventType` enum (zero consumers; the report-only replay verb emitted a command envelope, not this event).

## Outcome

- The operator help/risk surface no longer carries any reference to the retired replay verb; the `ledger.link` risk entry is unchanged (link is retained, now invoice-only). Risk-table parity + operator-surface contract suites pass on this surface (58 passed; the lone failure is exec-authcert-p04's `config rekey`->`config passphrase change` custody rename, out of this feature). Buckets domain suite 19 passed; ruff clean. Commit `d001678a0e`.

## Notes

- `_help.py` carried no removed-grammar references (the audit/link help text lives in the locale catalogues and CLI decorators, addressed in S13/S07).

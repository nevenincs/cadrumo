---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S29'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---




# Remove the attach_evidence double full-catalogue decrypt by threading one decrypted catalogue through the command

## Scope

- `src/aeat/application/ledger/_actions_manual.py`

## Description

- Add an internal `_preloaded_catalogue` param to `update_manual_transaction_fields`;
  when present it is used instead of `repository.load()`.
- `attach_manual_transaction_evidence` captures the catalogue it already loaded for
  validation and passes it through, eliminating the second full-catalogue decrypt.

## Outcome

A single `attach` no longer decrypts + parses the whole bucket transaction
catalogue twice. 304 ledger tests green. Committed in `b71c9e6fc`.

## Notes

The architectural fix (one secure-object row per transaction so single-row
mutations stop rewriting the whole catalogue) remains tracked as W06.P14.S31.

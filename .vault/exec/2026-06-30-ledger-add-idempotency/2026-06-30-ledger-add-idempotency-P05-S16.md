---
tags:
  - '#exec'
  - '#ledger-add-idempotency'
date: '2026-06-30'
modified: '2026-07-17'
body_hash: 'sha256:60c8ffe40c9dedefb9e822fa4e32b8e105db024db547db8d0702f959735c2c59'
step_id: 'S16'
related:
  - "[[2026-06-30-ledger-add-idempotency-plan]]"
---

# Add a strict Transaction save-load-equality roundtrip plus anti-tautology proof with the content fingerprint stamp populated non-default

## Scope

- `src/aeat/application/ledger/tests/`

## Description

- Add a create-path test proving a manually-created row's content fingerprint is non-default and survives an encrypted `TransactionCatalogueRepository` reload.

## Outcome

Landed in commit `3d8a6c14b`. The strict save->load->equality roundtrip and anti-tautology proof for the `Transaction` persistence boundary (including `import_fingerprint` non-default) already exist in `test_repository_roundtrip.py` and stay green; this step adds the create-path fingerprint-survival proof on top.

## Notes

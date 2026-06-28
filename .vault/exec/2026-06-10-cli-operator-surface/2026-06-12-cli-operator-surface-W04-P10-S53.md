---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S53'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W04.P10.S53 IVA Wallet Correction CLI Verb

Scope: verify `aeat app modelo iva-wallet correct`.

## Description

- Verified live help for `iva-wallet correct` requires `--confirm`.
- Ran IVA wallet inspector CLI tests.
- Ran documented-command conformance.

## Outcome

S53 is closed. The CLI exposes the guarded IVA wallet correction/read path.

## Notes

- Checks run: `pytest src/aeat/entrypoints/cli/tests/test_iva_wallet_inspector.py`.

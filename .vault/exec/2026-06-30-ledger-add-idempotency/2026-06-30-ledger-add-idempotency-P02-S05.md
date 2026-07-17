---
tags:
  - '#exec'
  - '#ledger-add-idempotency'
date: '2026-06-30'
modified: '2026-07-17'
step_id: 'S05'
related:
  - "[[2026-06-30-ledger-add-idempotency-plan]]"
---

# Stamp the content-only import fingerprint from derive_import_fingerprint onto manual rows at creation time, replacing the current import_fingerprint=None, without folding any timestamp

## Scope

- `src/aeat/application/ledger/_actions_manual.py`

## Description

- Default the content-only `derive_import_fingerprint` (amount, currency, direction, normalised narrative, effective date; no timestamp) in `_transaction_from_command` for any row built without a carried-forward fingerprint, i.e. every manual create path.
- Edit paths still pass the stored fingerprint verbatim, so it is stamped once at create and carried through edits.

## Outcome

Landed in commit `0c5b5da62`. Manual rows (previously `import_fingerprint=None`) now carry a 64-hex fingerprint; proven to survive an encrypted reload in `test_manual_add_idempotency.py`.

## Notes

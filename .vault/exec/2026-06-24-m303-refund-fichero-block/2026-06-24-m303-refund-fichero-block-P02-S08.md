---
tags:
  - '#exec'
  - '#m303-refund-fichero-block'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S08'
related:
  - "[[2026-06-24-m303-refund-fichero-block-plan]]"
---

# Refuse a refund disposition with no refund-account on file with an instructive typed error on the Notice channel, never an empty or partial DID block

## Scope

- `src/aeat/application/modelo/_export.py`

## Description

- Refuse a refund-disposition export that has no refund account on file with the typed `ModeloRefundAccountMissingError`, raised inside the header composer before any bytes are written.
- Refuse rather than emit an empty or partial cuenta-devolucion (DID) block, since a fichero with an empty DID page files a devolucion AEAT cannot pay.
- Route the refusal through the typed error class carrying a translated message so it surfaces on the operator Notice channel.

## Outcome

- `ModeloRefundAccountMissingError` is defined and exported in `src/aeat/application/modelo/_action_errors.py` and raised from the M303 export path when a refund disposition carries no `iban`.
- `test_modelo_303_refund_account_missing_e2e.py` asserts end-to-end that a REDEME refund export with no account is refused with the typed error and writes no fichero (neither the draft nor the receipt). Passes at HEAD.

## Notes

- This record documents the verified landed state at HEAD; the refusal fires before any draft write, so no partial artifact is produced.

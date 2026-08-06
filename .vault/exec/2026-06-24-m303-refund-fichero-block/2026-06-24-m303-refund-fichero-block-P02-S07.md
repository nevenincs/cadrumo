---
tags:
  - '#exec'
  - '#m303-refund-fichero-block'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:84788353645a9cad3673cd0cc7f5b222bfe7af5aea3404674c55112d5fcae16a'
step_id: 'S07'
related:
  - "[[2026-06-24-m303-refund-fichero-block-plan]]"
---

# Read the refund-account block from secure storage transiently and emit the IBAN, SWIFT-BIC, sepa_marca, and per-marca bank sub-fields only on a refund disposition

## Scope

- `src/aeat/application/modelo/_export.py`

## Description

- Read the refund-account block from encrypted secure storage transiently at export and populate the DR303 cuenta-devolucion (DID) page only on a refund disposition.
- Emit the IBAN at DID offset 23, the SWIFT-BIC at DID offset 12, the derived Marca SEPA at DID offset 194, and the per-marca foreign-bank sub-fields (name, address, city, country) for a non-SEPA (Resto Paises) account.
- Build the `RefundAccount` carrier from the profile facts and hand it to the header composer so the account data never reaches a log or plaintext side store.

## Outcome

- The M303 export path in `src/aeat/application/modelo/_export.py` imports `RefundAccount` and `derive_sepa_marca`, reads the account transiently, and emits the DID sub-fields keyed by the determined disposition.
- `test_export_refund_did.py` and the refund golden-SHA M303 cases assert the SEPA case emits IBAN-only DID fields and the non-SEPA case emits the full foreign-bank block, all at the DR303-prescribed offsets. Both pass at HEAD.

## Notes

- This record documents the verified landed state at HEAD; the refund-account bytes are held only transiently in memory during export, honouring the secure-storage-only mandate.

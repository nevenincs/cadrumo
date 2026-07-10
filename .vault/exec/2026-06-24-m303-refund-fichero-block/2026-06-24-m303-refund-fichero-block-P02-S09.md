---
tags:
  - '#exec'
  - '#m303-refund-fichero-block'
date: '2026-07-04'
modified: '2026-07-08'
step_id: 'S09'
related:
  - "[[2026-06-24-m303-refund-fichero-block-plan]]"
---

# Add the disposition-keyed conditional DID-page emission guard so a non-refund filing emits no empty DID page

## Scope

- `src/aeat/application/filing/_export.py`

## Description

- Add the disposition-keyed conditional emission guard for the cuenta-devolucion (DID) page in the filing export layer so a non-refund filing emits no empty DID record.
- Suppress the `page_did` record type when the disposition is not a refund, since a non-refund filing has no refund account to declare and an emitted DID page would write an empty fixed-width record the Diseno reserves for refunds.

## Outcome

- The `_did_page_suppressed` predicate and the `_DID_PAGE_RECORD_TYPE = "page_did"` constant live in `src/aeat/application/filing/_export.py`, gating DID-page emission on the refund disposition.
- The non-refund golden-SHA M303 case asserts the DID open tag and DID page identifier are absent and the fichero shrinks accordingly; the refund case asserts the DID page is present. Both pass at HEAD.

## Notes

- This record documents the verified landed state at HEAD; suppression mirrors the official DR303 structure, which emits the DID page only for a devolucion.

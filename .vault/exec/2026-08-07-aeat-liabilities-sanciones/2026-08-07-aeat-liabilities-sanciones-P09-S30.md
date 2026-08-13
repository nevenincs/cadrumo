---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:02df9dfcfac4f043e28d51abd54d51b48e880b751fd64eaeae4539bfd1998dd5'
step_id: 'S30'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---

# Add the frozen sancion/liquidacion parse record with Spanish-stemmed fields mirroring the printed labels (clave_liquidacion, referencia, nif, base_sancion, porcentaje_minimo, sancion_resultante, reduccion_conformidad, reduccion_pronto_pago, diferencia), each distinguishing an absent label from a matched zero, verified by a model unit test asserting a matched-zero and an unmatched field are not equal. DELIVERED as SancionLiquidacion rather than the row's original SancionDocumentoParse name, and the absent-versus-zero distinction is carried by Decimal | None on the optional fields rather than a per-field matched flag: a required field cannot express absence at all and refuses instead, so the flag would have been dead weight on every field that has one. Coverage is equivalent, not narrower - the regression pins that the arithmetic cannot recover the distinction, so only the record carries it

## Scope

- `src/cadrumo/adapters/inbound/notificacion/_sancion.py`

## Description

- Rename the percentage field to mirror the printed label, sweeping all ten sites in one commit with no alias left behind.
- Add a regression parsing both a printed zero reduccion and an absent reduccion line.
- Assert the two records are unequal while their derived totals and payable are identical.

## Outcome

Delivered, with two deliberate divergences from the row as originally written, both now carried in the row text itself.

The record ships as a sancion/liquidacion reading rather than the row's original parse-record name, because it carries the reconciled act, not a bag of matched labels. The absent-versus-matched-zero distinction is carried by an optional Decimal rather than a per-field matched flag: a required field cannot express absence at all - it refuses instead - so a flag on every field would have been dead weight on most of them.

The regression is the load-bearing part. It pins that a granted reduccion printed as zero and an ungranted reduccion produce records that are unequal, while the arithmetic derived from them is identical. That is the whole point of keeping the distinction on the record: no downstream total can recover it, so if the record collapsed the two, the information would be gone with nothing raising.

## Notes

The rename swept in a peer's concurrent conversion of the same test file from absolute to relative imports. A pathspec commit takes working-tree content, and the peer's edit landed between the read and the commit. Nothing was lost and the swept change is correct, but it carries this session's authorship rather than its author's. Recorded as a commit-hygiene incident, not a defect.

---
tags:
  - '#exec'
  - '#justificante-identity-matching'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:06759387248d9197550cb915efce0029107707f1b1a34391df8ad9a1622c2782'
step_id: 'S03'
related:
  - "[[2026-08-07-justificante-identity-matching-plan]]"
---

# Drop the now-signature-invalid expediente_id argument now that register_capture_as_filing_evidence's existing csv equality check already covers identity

## Scope

- `src/cadrumo/application/live/_justificante.py (register_capture_as_filing_evidence)`

## Description

`register_capture_as_filing_evidence` asserts the same CSV equality and raises
before calling `_justificante_matches_filing_record`.

## Outcome

Dropped `presentation_id=snapshot.expediente_id` from that call. Strictly
subtractive for the same reason as the sibling site.

## Verification

`test_stamp_refuses_when_snapshot_csv_disagrees_with_parsed_receipt` still covers
this site's genuine axis and passes.

## Notes

The sibling test that asserted the removed comparison was reframed rather than
deleted - see S05.

---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-11'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:178b6e206e847c3fc031716ee217d9ce5206dd6e002e8c1f86920326bca46391'
step_id: 'S30'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Apply row-level S3 grounding to tabular rows where base, cuota and total are present, gated by a defective-row fixture surfacing a closure finding

## Scope

- `src/cadrumo/application/ledger`

## Description

- Find which tabular lane can actually carry base, cuota and total together,
  rather than assuming the row's phrasing names one that does.
- Read each lane's own arithmetic treatment.
- Run the gates that hold it.

## Outcome

PREMISE EXPIRED. Row-level arithmetic closure on tabular rows is enforced at
HEAD, in both lanes, and more strictly than the row asks for -- a refusal
naming the terms rather than a finding to be reviewed.

There are TWO tabular lanes and the row's phrasing fits neither cleanly, which
is what made this worth measuring rather than building.

The bulk INVOICE import accepts a taxable base and a rate; the cuota and the
total are DERIVED. So a row where base, cuota and total disagree is not
constructible through it -- the identity holds by construction because the
lane never accepts all three. And where a row is malformed for any other
reason it is collected as refused, carrying its 1-based row number so the
refusal names the row an operator counts in a spreadsheet, while the valid
rows still import.

The ledger TABULAR import is the lane where all three genuinely co-exist:
gross, taxable base and cuota. It enforces
``gross == taxable_base + iva_amount + recargo_amount`` TO THE CENT at the
transaction model, and refuses with a message that reconstitutes the sum and
names each term rather than reporting a mismatch. A dedicated gate holds it,
thirty-three cases green.

So the finding the row wants surfaced is instead a refusal, and that is the
stronger of the two: a defective row cannot be confirmed past review, because
it cannot be constructed at all.

No change made. Closed on the measurement.

## Notes

The self-assessed arm is worth recording because it is the case that would
have looked like a defect to a fixture written against the row's phrasing: for
a self-assessed IVA operation the invariant becomes ``taxable_base == gross``
rather than the three-term sum, and it refuses on its own message. A
defective-row fixture built without knowing that would have read a correct
refusal as the wrong one.

Three unrelated failures observed in the same package while running the gates,
left to their owners: a peer added an IVA category member without its curated
prompt hint, and two split-lineage cases assert a hex-case rule that has moved.

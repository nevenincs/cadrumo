---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:6bc504c1f2ad62714a681bf1f6f72dd212e85c6c5e10384ccad96befe3caf729'
step_id: 'S30'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace unstructured-document-ingestion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S30 and 2026-08-07-unstructured-document-ingestion-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Apply row-level S3 grounding to tabular rows where base, cuota and total are present, gated by a defective-row fixture surfacing a closure finding and ## Scope

- `src/cadrumo/application/ledger` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

The self-assessed arm is worth recording because it is the case that would
have looked like a defect to a fixture written against the row's phrasing: for
a self-assessed IVA operation the invariant becomes ``taxable_base == gross``
rather than the three-term sum, and it refuses on its own message. A
defective-row fixture built without knowing that would have read a correct
refusal as the wrong one.

Three unrelated failures observed in the same package while running the gates,
left to their owners: a peer added an IVA category member without its curated
prompt hint, and two split-lineage cases assert a hex-case rule that has moved.

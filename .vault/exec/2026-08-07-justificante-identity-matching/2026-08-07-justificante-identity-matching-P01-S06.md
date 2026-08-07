---
tags:
  - '#exec'
  - '#justificante-identity-matching'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:0a550d72f34419531615f059a0dc640fa69a658e7bbf378a6304d7d35d3cc69a'
step_id: 'S06'
related:
  - "[[2026-08-07-justificante-identity-matching-plan]]"
---

# Add a real-fixture regression proving the register-reconciliation path enrolls a committed M303 justificante via the new csv-equality check

## Scope

- `src/cadrumo/application/live/tests/_filed_capture_history_support.py and a new or existing test in src/cadrumo/application/live/tests`

## Description

Two premises in the ADR and the dispatch brief were false against HEAD and are
corrected here. First, the committed Modelo 303 justificante fixture sidecars all
declare `provenance: synthetic_generated`; no `real_corpus` sidecar exists
anywhere under that fixtures tree. Second, the register-path test support built
`source_url` from the declarations LISTING URL, which carries no `CSV` query at
all, so the new check would have refused every existing fixture.

## Outcome

In `_filed_capture_history_support.py`: added a cotejo-document URL builder
mirroring the production shape, generalised the stored-observation helper across
modelos with an explicit `captured_csv` argument, added a Modelo 303 variant, and
generalised the filing seeder. The two fixture CSVs are stated as constants rather
than parsed back out of the PDFs - deriving them would make both sides of every
CSV comparison one value - and an anchor test keeps the constants honest against
the receipts.

Added `test_a_committed_modelo_303_receipt_is_enrolled_from_the_register_path`,
which asserts the receipt identifier and the register expediente id diverge FIRST,
so the fixture reproduces the divergence rather than sidestepping it, then asserts
enrollment. The 303 helper's default expediente id is register-shaped and
deliberately not the receipt's identifier; the 130 helper's default happens to
equal its receipt's identifier, which is what let the old conflated comparison
pass in tests while failing on every real capture.

## Verification

The test passes and would have failed before S01, since the old comparison
rejected every real Modelo 303 receipt.

## Notes

The fixture is a committed sanitised synthetic specimen. This record describes it
that way rather than repeating the ADR's real-corpus claim, which needs correcting
at its source. No operator profile bucket was read.

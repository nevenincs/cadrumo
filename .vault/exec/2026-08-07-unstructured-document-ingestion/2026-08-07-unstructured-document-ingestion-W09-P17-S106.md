---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-11'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:d0c2d76abb29b2d101ab23e265897db04987a355f8e862478a93cfc5144e52c3'
step_id: 'S106'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Extend the draft projection-parity gate to the nested envelope models, since it covers the top-level draft to extract-payload projection only and does not reach the field-provenance envelope to its payload counterpart, so a field added to the envelope sub-model breaks the operator confirm verb at the CLI boundary with no gate firing. That hole was walked through in practice when a provenance field gained a member its payload did not, and the payload forbids extras, so a valid command returned a refusal. Gated by the same property one level down and mutation-proven by adding a field to the envelope without its payload counterpart

## Scope

- `src/cadrumo/application/ledger/tests`

## Description

- Enumerate every draft sub-model and its payload counterpart, rather than the
  provenance envelope alone the row names.
- Measure the five pairs for divergence before writing the gate.
- Land the parity check one level down, both directions, with a floored pair
  table and constructed mutation proofs.

## Outcome

Delivered, and wider than the row asked. The row named the field-provenance
envelope; the same hole covers FIVE hand-mirrored pairs - line, rate
breakdown, ambiguity candidate, field provenance and discrepancy finding - so
gating one of them would have left four instances of the identical defect.

All five agree at HEAD, which is what made a hard cut affordable with nothing
to absorb and no baseline to store.

The failure mode is worth restating because it is the opposite of the
top-level one this gate family was built for. The waist gate exists against a
SILENT loss: a value read and then dropped, indistinguishable to the operator
from a value the document never stated. One level down the payload models
forbid extras, so the same divergence is LOUD and lands in the wrong place -
a correct operator confirm command returns a refusal. Same missing contract,
opposite symptom.

Both directions are checked. A missing payload field is a value the operator
never sees; a payload field with no draft origin is a claim nothing produces.
Mutation-proven both ways against constructed subclasses rather than by making
a production model wrong.

## Notes

The pair table is written out rather than derived by name, and the reason is a
vacuity risk rather than taste: the naming is not mechanical, so a
derive-by-convention rule would silently match nothing and the gate would pass
over an empty set. The table length is floored as a bound instead, so a pair
dropped from it fails while a sixth pair added does not demand a constant
update.

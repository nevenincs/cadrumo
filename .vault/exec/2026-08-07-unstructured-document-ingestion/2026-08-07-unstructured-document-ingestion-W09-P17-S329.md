---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:af4c4cf1c801c13e547be46b40b33a7a805f6a41aa02dae8e9321ab63a56fd20'
step_id: 'S329'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Collect the FLAT iva_rate in the establishment ladder's rate walk, which reads only the line and subtotal carriers and so sees nothing on the model-read lane. MEASURED 2026-08-12 by driving a text-lane draft through the real collector: lines and iva_breakdown are populated exclusively by the STRUCTURED reader, and a flat iva_rate exclusively by the model-read one, so the walk returned an empty tuple for every text and vision document. spanish_iva_charged is derived from that list alone, so the establecimiento-permanente contradiction lost its rate signal and the rung-3 non-establishment concordance lost a corroborator, on exactly the documents a model read. The sibling authority on the same question, draft_prints_a_repercutido_line, ALREADY reads the flat rate, so two functions in one package disagreed about what a document charged. Invisible because every rate test injects charged_iva_rates directly and none drives the collector from a draft

## Scope

- `src/cadrumo/application/ledger`

## Description

- Drive a text-lane draft through the real rate collector rather than reading
  it.
- Add the flat carrier, and gate every carrier from a draft rather than by
  injection.

## Outcome

Delivered. The ladder now sees a charged rate on every lane instead of on one.

MEASURED, not inferred. A draft in the shape a text or vision reader produces
-- one flat base, rate, cuota and total -- returned an EMPTY tuple from the
collector. The two carriers it walked, the line decomposition and the per-rate
subtotal block, are populated exclusively by the STRUCTURED reader; the flat
rate exclusively by the model-read one. So the walk collected nothing at all
for every text and vision document.

The consequence is not cosmetic. `spanish_iva_charged` is derived from that
list alone, and it feeds two things: the Spain-indicating signal behind the
establecimiento-permanente contradiction, and the corroborator that lets rung 3
resolve a foreign party silently. Both were dead on the model-read lane, so the
contradiction that the module says "fails loud" could not fire from a rate
there, and a foreign counterparty lost the second signal that would have spared
the operator a question.

THE TELL WAS ALREADY IN THE PACKAGE. The sibling authority on the same question
-- whether the document charged output IVA -- reads the flat rate and the flat
cuota, and always did. So two functions one directory apart disagreed about
what a document charged, and disagreed precisely on the lane a model reads. The
regime-contradiction check fired while the ladder saw no charge.

Why it survived: EVERY rate case in this package injects `charged_iva_rates`
directly into the resolver. Not one drives the collector from a draft. Injecting
the answer cannot test the question, and a collector blind to an entire lane is
exactly the defect that survives it. The gate added here drives from drafts, and
each of the three carriers is proved sufficient alone.

## Notes

FOUND WHILE MEASURING A DIFFERENT ROW, and that is the whole provenance. The
sibling contradiction-fixture row was being re-measured to test whether it
really depended on a pending tax review. It does. But reading the ladder to
answer that question surfaced this, which depends on nothing and had been silent
since the model-read lane existed.

THIS IS THE SAME DEFECT SHAPE CLOSED EARLIER TODAY IN THE CLOSURE IDENTITIES,
in a second place: the flat triple and the structured decomposition are DISJOINT
representations of one fact, populated by different readers, and a consumer that
walks one silently answers "no" for the other's entire population. Two instances
in one session is a pattern rather than a coincidence, and the general question
is worth carrying forward -- every consumer of a draft's tax figures should be
asked which carriers it reads, because reading a subset fails silently and looks
identical to a document that states nothing.

The ledger suite's five failures are unchanged by this and are not this surface:
they are error-message rendering failures against the in-flight error-code
rehoming. The IVA-domain failures that appeared alongside are a peer mid-sweep
adding a new category member ahead of its tests; the domain does not import this
module, and the direction of dependency forbids it.

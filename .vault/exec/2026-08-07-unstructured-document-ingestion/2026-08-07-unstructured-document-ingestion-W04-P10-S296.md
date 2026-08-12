---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-11'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:5cbc94f9707f5feba7abbb998af61fc780b79dd55abe72739e66b4f06345ee2c'
step_id: 'S296'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Score the draft the reading ROUTER hands on rather than the extractor's raw output, since suggested_kind is derived deterministically by ground_draft_against_transcription from the filer tax id one stage AFTER ground_extracted_fields, and iva_category is decided by the single classification authority at the confirm boundary. A capture taken at the extractor stage reports both None and cannot distinguish never-produced from produced-one-stage-later, which is what motivated a proposal to route both through the LLM classifier and would have replaced two deterministic authorities with probabilistic ones

## Scope

- `dev/ingest_harness/_runner.py`

## Description

- Confirm the row's diagnosis and find where a stage guard could live.
- Attempt it at the projection boundary, meet the module's own design pushing
  back, and revert.
- Re-open on the finding that the guard needs the scored field NAMES, and
  measure whether it actually does.
- Declare the producing stage per key field, refuse a row that scores a slot
  its stage cannot carry, and gate both halves.

## Outcome

DELIVERED, in the instrument. An earlier pass closed this as caller-only work
and that conclusion was WRONG on one load-bearing step, which is recorded below
rather than quietly replaced.

The diagnosis was always right. Neither field is read off the page: the
suggested kind is derived deterministically from the filer's own tax id one
stage after extraction, and the IVA category is decided by the single
classification authority at the confirm boundary. A capture at the extractor
stage reports both absent, so scoring them books two DETERMINISTIC fields as
model misses. That already had a consequence: an identical residual across
every pilot document motivated a proposal to route both through the LLM
classifier, which would have replaced two deterministic authorities with
probabilistic ones.

THE FIX IS A REFUSAL, NOT A CAPTURE MOVE. The harness cannot move a capture it
does not own, but it can refuse to report a figure the capture cannot support,
and that is its stated job -- rows are validated on the way IN precisely so an
unquotable row cannot sit in a report until someone renders it. Refusing forces
the caller to move the capture, which is what the row asked for, enforced in
the instrument instead of left to the caller's discipline.

So the map now declares `available_from` per key field: the grounding seam for
the derived kind, the classification seam for the IVA category, extraction for
everything else, which is where the reading contract's own fields appear. A
predicate compares a row's declared stage against each scored slot's own, and
the report refuses with the unreachable slots NAMED, so the caller learns where
to move rather than only that something is wrong.

MEASURED, and the number is the argument: of 302 documents on the pinned key,
221 author at least one slot the extraction seam cannot carry, and 29 still do
at grounding. None do at classification. A capture at extraction was
mismeasuring most of the corpus.

Emitted-only rows are exempt and the reason is not convenience: such a row
counts what a stage produced and claims nothing about what the document
authored, so there is no denominator to inflate and no reader being scored.

Kept distinct from the `category_scorable` hint on purpose, and the code says
so: that hint is the CORPUS stating whether a document's category truth can be
scored at all, and this is the PIPELINE stating whether the capture point could
have produced it. Two questions that look alike and answer differently.

## Notes

CORRECTION TO THIS RECORD'S OWN EARLIER CLOSURE. The prior pass concluded the
runner could not carry the guard because "its row record carries counts rather
than the scored field NAMES -- so it cannot see which fields a row scored".
The first half is true and the inference does not follow. The guard never
needed the scored names: a scored row's denominator is REQUIRED to equal the
document's authored slot count, so every authored slot is scored by
construction, and the report already resolves the document. The names were
available all along, from the key rather than from the row.

That is worth keeping because the earlier finding was careful, specific, and
correctly reverted two bad placements -- and still reached the wrong verdict by
one inferential step. A blocked-here conclusion is a claim like any other and
deserves the same re-measurement as a defect.

Two placements the earlier pass refused stay refused, and its reasoning stands:
the projection function is declared DATA rather than translating code, and a
refusal there breaks its own unit tests correctly. The guard sits where the
refusals already live.

One hazard found and closed while building: the predicate must NOT expand the
document's slots itself. A caller has usually expanded before scoring, and
expanding again drops every composite leaf, whose slot name is not a key field
-- so an internally-expanding predicate would silently stop seeing the
composite half of exactly the documents that had been through the normal path.
Reading the truth as given and splitting the composite prefix before lookup is
correct for both shapes, verified across all 302 documents and locked by a
case.

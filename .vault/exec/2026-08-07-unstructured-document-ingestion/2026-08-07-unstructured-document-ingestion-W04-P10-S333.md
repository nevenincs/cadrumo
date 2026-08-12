---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:a102497caeb806418001182a9c2cc5b9c123cc697cbe096ad14c75096b4ecbc8'
step_id: 'S333'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

## Description

- Restore the row, whose own record says the step was never delivered while the
  row had been retired.
- Measure the blocker rather than assume it, and correct the first answer.
- Build the caller the runner was written for, and run it.

## Outcome

Delivered as far as code can take it: the instrument has a caller, and it runs.

THE ROW WAS INVISIBLE RATHER THAN MERELY OPEN. Its exec record states plainly
that the step was NOT delivered -- it verified the corpus key and refused to
report a direction without a run, on the grounds that asserting one would defeat
the row rather than close it -- and the row had been retired anyway. So the plan
showed nothing open for a question the ADR still holds open and calls resolvable
only by measurement, never by assertion. That is the failure mode where
delivered, delivered-narrower and never-delivered stop being distinguishable:
here it was worse, because the row was simply gone.

THE FIRST BLOCKER I NAMED WAS WRONG and is corrected in the row rather than
quietly replaced. I reported the runtime -- ollama installed but unreachable,
`qwen3:1.7b` unpulled -- and told the operator to start it. Starting it would
not have enabled anything: `HarnessReport` was constructed ONLY in the harness's
own tests, so nothing in the repository could point the instrument at a
document. The package says as much about itself: it is the instrument, and the
measurement steps supply the engines that drive real entry points. The binding
blocker was a missing driver, and a runtime is downstream of it.

WHAT LANDED is the plumbing between three shipped pieces -- the product's own
reader, the corpus-to-draft projection, and the scorer -- reimplementing none of
them. That restraint is the point rather than a preference: a 409-line shadow
parser was deleted from an earlier harness because a harness that reimplements
the reader measures itself.

IT RUNS, on a machine with no inference runtime at all. The structured lane is
deterministic, so a Facturae, UBL or CII record reads reproducibly and its
numbers do not move between runs. Over the pinned corpus the driver produces 26
accepted rows across 391 authored slots, and the runner's own honesty refusals
fire on the rest -- documents authoring no truth, and denominators that are not
the key's own. Those refusals firing THROUGH the new path is what shows the
driver did not become a way around the instrument.

The row states its route as DETERMINISTIC rather than a local inference route,
because no model runs; and its tier sets no acceptance floor, because a floor
drawn from a parser would flatter every model-read lane compared against it.
Stage is stated rather than inferred: the runner refuses a row whose declared
stage cannot produce a slot the document authors, and guessing it here would
quietly satisfy a check written to catch exactly that.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

WHAT THE ADR'S QUESTION STILL NEEDS IS A RUNTIME, and that is genuinely the
operator's to supply rather than code anyone can write: the call-shape question
is about how a LOW-CONTEXT MODEL behaves across two prompt shapes, so it cannot
be answered on the deterministic lane at all. The instrument can be pointed the
moment a runtime exists. That is a materially different position from where this
row started, where nothing could be pointed at anything.

NO ACCURACY FIGURE IS ASSERTED IN THE SUITE, deliberately. A number pinned there
becomes a target and goes stale against a corpus that grows; what the cases hold
is that real documents produce quotable rows, that the reader is the product's
own, and that every refusal the runner exists for still fires.

An AEAT SII or VeriFactu payload is a reporting submission rather than an
invoice record, so the product's reader refuses it correctly. The driver
surfaces that as its own error instead of scoring a document it never read,
which would have booked a reader's correct refusal as a measurement failure --
and a case asserts that path is exercised rather than assumed.

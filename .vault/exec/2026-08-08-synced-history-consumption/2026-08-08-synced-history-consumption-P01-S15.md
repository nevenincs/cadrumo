---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:a087642e0dd8b04d8aa4efdd30676416863e2d21c32bcf4c4ee7a662b4156f6b'
step_id: 'S15'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
  - "[[2026-08-08-synced-history-consumption-adr]]"
---

# Stop the filed-capture refusal asserting an AEAT fact it cannot know

## Scope

- `src/cadrumo/application/live/_filed_data_capture.py`

## Description

- Check the row against HEAD before dispatching it.
- Read the shipped refusal text rather than the commit subject that changed it.
- Confirm the row's three gate conditions are each held by a test.
- Record the delivery so the row closes with evidence rather than a checkbox.

## Outcome

THIS ROW WAS ALREADY DELIVERED WHEN THE CAMPAIGN OPENED IT, and the record says
so rather than claiming work.

The row objects to a refusal that told an operator "AEAT declarations register
does not offer modelo 200" — a claim about AEAT's coverage that was only ever a
claim about this deployment's own registry. At HEAD the refusal states that the
modelo declares no authenticated filed-declarations read surface in this
deployment's registry, that the register was therefore not queried for it, that
whether AEAT serves the modelo at the consulta view is not recorded here, and
that running the filed discovery verb reads the register's own modelo list and
settles it. Each of the row's three gate conditions is met: no operator-facing
string asserts what AEAT does or does not offer on the basis of a registry
silence, the refusal still names the modelo and stays actionable, and it names
what would settle the question rather than leaving the operator with a dead end.

THE GATE IS THREE TESTS, NOT ONE, and the third is the one that matters most.
Two assert the refusal's content for a modelo with no declared read surface — it
claims nothing about AEAT, and it says what is true plus what the operator can
do. The third asserts that a modelo which DOES declare the surface is not refused
at all. Without that third case the first two would pass on an implementation
that refused everything, which is the shape where a correct-looking assertion
proves nothing about the discrimination it is supposed to be testing.

WHY THE ROW LOOKED OPEN. Same cause as its sibling in the other plan: the fix
landed on the day the plan was authored and the two never reconciled. Nothing was
wrong with either.

## Notes

THE INFERENCE THE ROW FORBIDS IS THE DURABLE PART, and it outlives this fix. Our
registry's silence about a modelo is evidence about our registry, never about
AEAT's published surface. The corrected text is careful to say only what is
knowable from inside this deployment and to name the one authenticated read that
would settle the rest — the register's own modelo combobox. Any future refusal on
this surface has the same obligation, and the temptation to phrase it as a fact
about AEAT will recur because that phrasing reads as more helpful.

THE SIBLING QUESTION IS STILL OPEN AND IS NOT THIS ROW. Whether AEAT actually
serves Sociedades declarations at the consulta view remains unsettled and is
answerable only by one authenticated operator run. This row fixed the CLAIM; it
did not and could not answer the underlying question, and the two must not be
read as one.

NO CODE WAS WRITTEN FOR THIS ROW. The record closes the gap between delivered and
recorded-as-delivered. The verification check that found it is the standing rule
that an unchecked row is not evidence the work is undone — the same pass found
one row in the sibling plan in the identical state.

---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-11'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:7d5c23ebd0093bdb03be3e070321d3349b6201c505592fbe9127db227cb2f9e0'
step_id: 'S126'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Make the evidence-confirm CLI suite runnable without a live local model, since all seven cases fail at the extraction stage on a local inference connection failure before reaching any confirm logic, which makes the whole file dead coverage for anyone working this surface. Six of the seven fail identically on an untouched tree so it is environmental rather than a regression. Use the deterministic structured fixture the document-identity gate uses, which needs no reader at all and is why that gate runs where this one cannot

## Scope

- `src/cadrumo/entrypoints/cli`

## Description

- Reproduce the reported failure and confirm the cause is the reading lane.
- Switch the suite's document from a generated text PDF to a bundled Facturae
  document, so the lane is the deterministic parser.
- Restate every expectation from the bundled document's own values.
- Chase the two blockers that surfaced behind the first, and fix the second at
  the shared harness rather than in this file.

## Outcome

Delivered. The suite runs with no model reachable, and the sibling
duplicate-confirm suite with it.

THREE blockers, stacked, and only the first was the one the row named. Each
was invisible until the one above it was cleared, which is why the row's
"environmental rather than a regression" framing was right about the kind of
problem and short on its depth.

First, the reading lane. A generated text PDF reads through the semantic
extraction stage, so every case failed on a local inference connection failure
before reaching any confirm logic. A bundled Facturae document reads through
the deterministic parser instead: no model, and every re-read resolves the
same figures.

Second, the profile. With the model out of the way the confirm path reached
the IVA treatment and the deadlines profile refused: the Modelo 303
composition was never declared, then four more IVA axes behind it. Correct in
production - an undeclared composition is not a general one - but it arrives
before the behaviour under test.

Third, and the finding worth carrying: that profile gap was NOT local to this
file. Measured across the ledger CLI integration surface, ONE cause accounted
for roughly thirty red modules, because a peer lane made the IVA block
mandatory without sweeping the shared test harness. So the declaration went
into the shared session helper rather than into this suite, and the surface
went from 103 failures to 68 in one change. The remaining 68 are other causes
and other lanes.

## Notes

WHAT THIS COST, recorded so the row does not read as delivered in full. One
property left the CLI layer. The suite used to prove that a required field
with no extraction heuristic and no override refuses rather than being
fabricated, and it proved that by omitting the counterparty name from a
document the reader could not recover one from. A structured document names
its parties, so that state is not constructible from the bundled corpus: the
only bundled document with an unnamed side leaves it on the BUYER, and
confirming that document as ISSUED is refused earlier and for a better reason,
because it names an issuer who is not this filer. The refusal now asserted is
that wrong-side one, which is genuine and worth pinning - an invoice confirmed
on the wrong side lands as income instead of expense and aggregates that way
into every downstream modelo. The missing-required-field refusal wants an
application-layer case over a constructed draft, needing neither model nor
document, and is rowed separately rather than absorbed here.

TWO further findings, neither this row's to fix. The confirm path compares a
supplied counterparty identifier against the extracted one with the identity
token, which is trim-and-uppercase and nothing more, so a document stating the
VAT form and an operator supplying the bare national form are refused as a
mismatch on what is the SAME BEARER. That is the same over-refusal shape an
open row already names on the separator axis, and this is a second axis of it;
the case that hit it drops the override rather than encoding the defect. And
the remaining 68 red modules on this surface are dominated by an unrelated
quiet-mode harness change, left to its owner.

The two source files here were swept into another lane's commits mid-flight,
which is the shared-tree hazard rather than a problem with the work: the
content at HEAD was verified to be the final state before this record closed.

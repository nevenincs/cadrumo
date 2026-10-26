---
tags:
  - '#adr'
  - '#facturae-invoice-class'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:2e012de314f0ff3008e6ef6ece87d10035a29f47806f22dbef0778f5b1744350'
related:
  - "[[2026-08-12-facturae-invoice-class-reference]]"
---

# `facturae-invoice-class` adr: `the declared code grounds the class, and the two axes it carries are not collapsed` | (**status:** `accepted`)

## Problem Statement

A Facturae record states its own class in `InvoiceClass`, and the reader ignores
it. The invoice class is instead INFERRED downstream: a draft that resolved a
corrective reference is reclassified from ordinaria to rectificativa. That
inference is sound and grounded, but it derives a fact from the PRESENCE of a
sibling field while the document declares the fact outright a few elements away.

The code set was unavailable when the reader was written, which is why it was
skipped. It is now bundled with byte-verified provenance
(`2026-08-12-facturae-invoice-class-reference`), so the reason no longer holds.

## Considerations

- The declared code is evidence; the corrective reference is a correlate. Where
  both exist they agree, and where they disagree the document contradicts itself
  — which is worth surfacing rather than silently resolving.
- The code carries TWO axes at once: original versus copy, and ordinaria versus
  rectificativa versus recapitulativa. Six values, a 2x3 product.
- The domain's `InvoiceClass` answers a different question and has a different
  membership: `ORDINARIA`, `SIMPLIFICADA`, `RECTIFICATIVA`, closed by RD
  1619/2012 art. 6.1.a. `SIMPLIFICADA` has no Facturae counterpart,
  *recapitulativa* has no domain counterpart, and the copy axis has no home at
  all.
- Existing corpus fixtures already carry `OO` and `OR`, so the change is
  testable against real records rather than synthetic ones.

## Considered options

**Read the code and ground the class on it, keeping the inference as fallback.**
Chosen. Evidence outranks correlate; a document declaring nothing still gets
today's answer.

**Map all six codes onto the domain enum.** Rejected. It is lossy in two
directions at once: `OC`/`CC` would have to become `ORDINARIA`, silently
discarding that the document declares itself recapitulativa, and the copy axis
would vanish entirely.

**Add `RECAPITULATIVA` to the domain vocabulary now.** Rejected for this change,
deferred as its own. A factura recapitulativa is real — RD 1619/2012 art. 13 —
and it belongs in the domain eventually, but adding a member to a closed
regulatory taxonomy reaches every consumer of that enum and needs its own
grounding pass. Bundling a vocabulary and widening a domain taxonomy are
different acts.

**Replace the corrective-presence inference.** Rejected. A record may declare no
class, and dropping the inference would lose the population it already serves.

## Constraints

- The reader must not refuse a document over this axis. An unrecognised or absent
  code leaves the class exactly where it is today.
- The copy axis is READ but not acted on. Nothing downstream distinguishes a copy
  from an original, and inventing a behaviour for it here would be a decision
  taken in the wrong place.

## Implementation

The parser reads `InvoiceClass` from the header into a typed field on the parsed
record, validated against a closed enum whose members are the six bundled codes.

The draft assembly then grounds the class on the declared code where one is
present: `OO`/`CO` are ordinaria, `OR`/`CR` are rectificativa. `OC`/`CC` declare
themselves recapitulativa, which the domain cannot express — so they are left at
the operator-stated class and carry a discrepancy finding saying the document
declares a class the application does not model, rather than being flattened into
ordinaria.

Where the declared code and the corrective reference disagree — a record stating
`OO` while carrying a `Corrective/InvoiceNumber`, or stating `OR` with none — the
document contradicts itself and that is reported, not resolved.

## Rationale

The knockout is that the class is a printed, declared fact and the application
was deducing it. Every other axis in this reader takes the document's own
statement when the document makes one; this one did not, for a reason that has
since been removed.

The refusal to collapse the two axes is what keeps the change honest. A mapping
that produced an answer for all six codes would look more complete and would be
asserting, for two of them, something the document does not say.

## Consequences

A rectificativa declaring `OR` is classified from its own statement rather than
from the presence of a corrective reference, and a self-contradicting record is
surfaced instead of silently taking one of its two answers.

Recapitulativa records remain unmodellable, now visibly: the operator sees a
finding naming the gap instead of an invoice quietly classified as ordinaria.
That is the carry-forward this change creates, and it is the honest form of a
gap the previous silence hid.

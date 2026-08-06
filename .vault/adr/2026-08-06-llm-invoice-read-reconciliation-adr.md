---
tags:
  - '#adr'
  - '#llm-invoice-read-reconciliation'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:2de8a4e3e0dc5795dbeb7b0d623f525660ecf620e0cce75dcee98647880074d2'
related:
  - "[[2026-08-06-llm-invoice-read-reconciliation-research]]"
---
# `llm-invoice-read-reconciliation` adr: `Direction-aware evidence reading, and the two questions the invoice-read path cannot answer alone` | (**status:** `proposed`)

## Problem Statement

The `evidence confirm` verb accepts `--kind issued` and routes it to the invoice writer,
but no accepted ADR has ever scoped evidence extraction to that direction. The governing
record, `2026-05-30-purchase-invoice-ocr-extraction-discipline`, states its document class
as operator-uploaded SUPPLIER invoices; its six mentions of "issued" all refer to
AEAT-issued modelos, not to invoices the taxpayer issues.
`2026-06-10-llm-evidence-classification`, which resolved that record's deferred engine
choice by selecting the on-host model read, does not mention the issued direction at all.

So the purchase shaping documented in `2026-08-06-llm-invoice-read-reconciliation-research`
is not drift and not an oversight in the code: it is faithful implementation of a
discipline that was scoped to one direction by decision. What changed underneath it is that
the confirm surface grew a `kind` axis accepting both. The result is a reachable operator
path with no governing discipline behind it, and the research measured what that costs --
on an issued invoice the reader returns the filer's own identifier, which reaches the
Modelo 347 and 349 counterparty totals AEAT reconciles against the counterparty's own
filing.

A decision is needed now rather than a patch because the correction is not local. The
prompt, the tax-id selection heuristic, the draft field naming, the evidence record's
missing direction axis, and the CLI review hint all encode the single-direction assumption,
and moving any one of them alone leaves the operator in a worse position than moving none.

Two further questions surfaced in the same investigation that this record deliberately does
NOT decide, because neither can be settled from the evidence-read path alone. They are
stated below so the next reader inherits the question rather than re-deriving it.

## Considerations

- The single-direction scope is inherited from an accepted ADR, so this record must extend
  that discipline explicitly rather than contradict it silently -- the same obligation
  `2026-06-10-llm-evidence-classification` accepted when it re-targeted the same record's
  engine deferral.
- The safety floor is already in place: a self-naming counterparty is refused at the confirm
  boundary as of commit `6d49d3a2aa`. That closes the harm but not the capability, and the
  distinction matters for sequencing -- nothing here is urgent in the way the guard was.
- Counterparty identity is externally checked. Modelo 347 and 349 are informativas AEAT
  reconciles against the counterparty's own declaration, so a wrong value is visible from
  outside and reaches the taxpayer as a discrepancy notice.
- Direction is available at the call site and discarded: `confirm_invoice_draft_from_evidence`
  holds `kind` and does not pass it to extraction.
- The evidence record has no direction axis and excludes one from its id derivation, so two
  records differing only in direction collide -- a storage-level constraint on any fix that
  tries to record direction at `evidence add` time.
- The amount, date, number and currency heuristics are direction-agnostic; the research
  refutes the intuition that `iva repercutido` indicates purchase shaping. Only counterparty
  identification is direction-sensitive, which bounds the change.

## Considered options

- **Do nothing; rely on the self-counterparty guard.** Cheapest, and the harm is already
  refused. Rejected: it leaves the issued direction permanently unusable, because the
  operator must supply `--counterparty-nif` on every issued invoice with no indication that
  this is required, and the reader still offers them a value that is wrong.
- **Anchor tax-id selection on document labels only, without threading direction.** Locate
  "Cliente"/"Destinatario" versus "Emisor" and pick accordingly. Rejected as insufficient
  alone: a document that labels neither party falls back to first-match, which is the
  current defect; and the vision prompt would still ask for the supplier explicitly.
- **Thread direction through extraction and parameterise both readers on it.** Chosen. The
  prompt states which party to return, label anchoring resolves it on the text-layer path,
  and the draft field is renamed to a direction-neutral counterparty. Costs a signature
  change on the extraction primitive and a rename with consumers.
- **Record direction on the evidence record at `add` time.** Rejected for now as a larger
  change than the problem requires: the id derivation excludes direction, so adding it
  changes stored identity, and direction is already known at confirm time where it is
  needed. Worth revisiting if evidence listing ever needs to show direction.
- **Refuse `--kind issued` outright until the reader supports it.** Honest, and briefly
  tempting. Rejected: it removes a working path -- an operator who supplies the customer's
  tax id explicitly gets a correct record today -- to protect against a default that the
  guard already refuses.

## Constraints

- Must not weaken the regulated-number discipline. Direction changes WHICH party the reader
  identifies; it must not become a route by which any numeric tax field becomes
  model-emitted.
- Must not alter the `Invoice` domain model, which stays free of profile dependencies.
- The renamed draft field is operator-visible in the extract JSON payload and the CLI text
  output, so the rename is a surface change and must move with its documented-command
  conformance and schema gates.
- Real-behaviour tests only; the issued direction currently has three tests, all added with
  the self-counterparty guard, and every other test on this path exercises the received
  direction.
- No vision model was executed during the research, so the claim that a model obeying the
  prompt returns the filer's identifier on an issued invoice is reasoned from the prompt
  text. Any implementation should measure it rather than inherit the assumption.

### Operator ruling required, question one: the domestic-vs-not discriminator

`iva_category` is load-bearing on the income path, and no CLI surface can set a domestic
one, so every domestic invoice from every path is currently ungrounded -- measured in
`2026-08-06-llm-invoice-read-reconciliation-research`. A closed rate-to-category mapping
already exists, and the research records that it is already consumed for a different
purpose -- per-line Modelo 303 settlement observations -- so this is not a matter of
switching on idle capacity.

What makes this hard, and what stops it being fixed in an afternoon: that mapping is
domestic-only. Deriving a category from the rate slot alone would stamp
`DOMESTIC_GENERAL_21` on an export or an intra-community supply. A wrong category is worse
than an absent one, because the absent one is refused and the wrong one is believed.

The readings are: derive domesticity from `counterparty_country`, which is already on the
invoice but defaults to `ES` and would therefore silently claim domesticity for an unstated
counterparty; require an explicit operator declaration, which is honest but adds a mandatory
field to every invoice-creating surface; or keep the category absent and treat the resulting
degradation as correct until an operator states it, which preserves current behaviour and
leaves every domestic invoice degraded.

One fact bears on the choice more than the rest, and it is a precedent rather than an
argument. The codebase ALREADY answers this question in production, and answers it the
first way: the Modelo 303 invoice-observation gate decides domesticity solely by
`counterparty_country` equal to `ES`, and reads no category at all. So the first reading
would make one discriminator where there is currently one, and either of the others would
make two that must agree.

That same precedent carries the hazard the first reading is criticised for, already live:
the country it tests defaults to `ES` at both the CLI option and the application boundary,
so an invoice whose counterparty country was never stated is already treated as domestic
for Modelo 303. Whoever rules on this should decide the default at the same time, because
choosing the discriminator does not by itself make the fact declared.

Scope worth knowing before ruling, because it narrows the urgency: the missing category does
NOT break the IVA path. The Modelo 303 observations derive their settlement side from the
rate and the invoice direction, both of which the evidence path does set, so an
evidence-confirmed domestic invoice reaches Modelo 303 with correct devengada/deducible
routing. The degradation is confined to the renta income path, which reads the category.

This record does not choose. Whoever does should note that the third reading is the status
quo, so "no decision" is not neutral -- it is a choice for permanent degradation on the
income path.

### Operator ruling required, question two: the transcribed taxable base

`2026-06-10-llm-evidence-classification` requires that the response schema make it
structurally impossible for the model to emit `taxable_base`, and states that evidence
reading does not relax this. The confirm path mints a standalone catalogue invoice with no
linked transaction, so the derivation that constraint assumes -- base from gross and rate --
has no input. Read literally against this path, the constraint forbids standalone invoice
creation entirely.

The readings are: require the confirm to be transaction-linked so a gross exists; amend the
constraint to permit a transcribed base on the standalone path with the printed-total
cross-check landed in commit `3e3ae28d04` as the compensating control; or require an
explicit operator-supplied base and demote the extracted value to advisory.

This is a gap in the constraint rather than a violation of it, and it is not this record's
to close.

## Implementation

Extraction gains a direction parameter. `confirm_invoice_draft_from_evidence` passes the
`kind` it already holds down through `extract_invoice_draft_from_evidence` to both readers.

The vision prompt becomes a function of direction rather than a module constant, naming the
party to transcribe -- the customer on an issued invoice, the supplier on a received one --
and keeping every other instruction, including the verbatim-transcription and null-when-absent
rules, unchanged.

The text-layer path gains label anchoring: candidate tax ids are preferred by the Spanish
invoice label nearest them, with the direction selecting which labels are counterparty
labels. Unanchored first-match survives only as the last resort it already is, and a
document that labels neither party therefore behaves no worse than today.

`InvoiceDraft.supplier_tax_id` becomes `counterparty_tax_id`, matching what the field has
always fed. The extract JSON payload, the CLI text line and the `--counterparty-nif` help
move with it.

The CLI review hint derives its `--kind` from the same signal instead of hardcoding
`received`, and `evidence extract` gains the `--kind` option it needs to produce a
direction-aware read at all.

The self-counterparty guard stays exactly where it is. It is the floor beneath this work,
not a step in it: even a direction-aware reader can misread, and the guard is what makes
that misread loud.

## Rationale

Threading direction wins because it is the only option that makes the reader CORRECT rather
than merely making it fail safely. The self-counterparty guard already makes the current
failure loud, so the remaining value is entirely in identifying the right party, and no
option that leaves the prompt asking for the supplier can do that.

Label anchoring alone was the closest alternative and is a component of the chosen option
rather than a rival to it. What it cannot do on its own is instruct the vision reader, which
is the path that handles scanned and photographed invoices -- the ones most likely to reach
this surface from a phone camera.

Scoping the change to counterparty identification is what keeps it proportionate. The
research refutes the broader claim that the heuristics are purchase-shaped throughout, so
this is a bounded change to one axis rather than a rewrite of the reader.

## Consequences

The issued direction becomes a supported path rather than a reachable one, which is the
precondition for the invoice-reading parity the wider goal asks for -- deductible versus
payable IVA, deduction recognition and withholdings all presuppose knowing whose invoice is
being read.

The rename is the main cost. `supplier_tax_id` appears in an operator-facing JSON payload,
so consumers outside this repository would see a field change; within it the conformance
gates will catch every site.

Two capabilities remain absent afterwards and should not be mistaken for delivered. Recargo
de equivalencia still cannot be captured on this path; commit `3e3ae28d04` makes the loss
visible, not repaired. And `iva_category` remains unsettable for domestic invoices until
question one is answered, so a direction-aware reader still produces records the income path
degrades.

A pathway this opens: once direction is threaded, the evidence record's missing direction
axis becomes the natural next question, and with it the ability to list evidence by
direction rather than presenting every stored document as a supplier invoice.

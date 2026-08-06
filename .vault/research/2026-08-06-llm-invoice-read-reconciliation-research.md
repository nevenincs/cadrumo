---
tags:
  - '#research'
  - '#llm-invoice-read-reconciliation'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:31f45ff479848fbf5df0f95f50749f36122c5c0dce9d87267cc20dd5bf62a89b'
related: []
---
# `llm-invoice-read-reconciliation` research: `What the evidence-read path does and does not know about the invoice model`

The `Invoice` record grew substantially over one working day: `recargo_amount` joined the
totals identity (commit `bf2a0c880a`), `iva_category` became load-bearing on the income
path (commit `e173f8e493`), and `operation_date`, `operation_date_role`, `suplido_amount`,
`InvoiceClass`, `series` and `rectifies_invoice_number` landed together (commit
`1751ce04cf`). The evidence-read path -- the on-host text-layer extractor and its local
vision fallback, which together are how a document becomes an `Invoice` -- did not move.

The question was whether that path had DRIFTED from the model or had never implemented
these axes at all, and what it costs the taxpayer either way. Every claim below was
measured by running the real path against real encrypted storage, not read off the source.

The short answer: it never implemented them. `InvoiceDraft`
(`src/cadrumo/application/ledger/_evidence_draft.py:192`) carries eight fields -- supplier
tax id, invoice number, invoice date, taxable base, IVA rate, IVA amount, grand total,
currency -- and has no counterpart for any axis added since. This is not decay; the reader
was built for a simpler `Invoice` and the model moved past it.

## Findings

### Every domestic invoice is ungrounded, from every path, because no surface can set a category

Running `confirm_invoice_draft_from_evidence` end to end and passing the result to
`decompose_invoice` yields `is_grounded = False` with defect `iva_treatment_undeclared`.

The cause is not the evidence path. The only production assigner of a catalogue invoice's
`iva_category` is `_catalogue_iva_category_for_operation_type`
(`src/cadrumo/entrypoints/cli/_ledger_business_invoice_cli.py:132`), which maps
`--operation-type E|A|T` onto the three intra-community categories and returns `None` for
everything else. The `evidence confirm` verb exposes no `--iva-category` option at all. A
plain domestic invoice therefore has no way to acquire a category through any CLI surface,
so the coherence guard added by `e173f8e493` degrades all of them.

The guard itself is correct: a record with no declared category genuinely cannot be
decomposed, because field nullness cannot distinguish "this component does not exist in
law" from "nobody recorded it" (`src/cadrumo/domain/invoices/_decomposition.py:1`). What is
missing is the data-entry surface that would let an operator satisfy it. The guard shipped
ahead of its input.

A closed rate-to-category mapping already exists: `classify_invoice_line_for_iva`
(`src/cadrumo/domain/iva/_invoice_classification.py:158`) derives an `IvaCategory`, a flow
direction and a rate kind from `(iva_rate, invoice_kind)`, and `build_catalogue_invoice`
already holds both inputs.

It is NOT idle capacity, and an earlier draft of this document said it was. The mapping is
consumed in production through `invoice_line_to_iva_observation`
(same file, line 221, which calls it at line 267), which
`src/cadrumo/application/aggregation/_modelo_bindings.py:1097` calls to build the
invoice-derived Modelo 303 observations. The error came from a symbol sweep that excluded
the mapping's own package and so never saw the intermediate hop; the module's own docstring
states the consumer chain plainly. Recorded because the wrong conclusion is the more
attractive one -- "unused deriver, wire it up" is a tidier story than what is actually true.

What is true is narrower and still blocking. The mapping already has a job -- per-line
settlement observations -- which is a different question from what category the invoice
RECORD carries, and it is explicitly domestic-only
(`_iva_rate_to_domestic_category`, same file, line 78). Applying it to set a record's
category would stamp `DOMESTIC_GENERAL_21` on an export or an intra-community supply -- a
wrong category is worse than an absent one, because the absent one is refused and the wrong
one is believed. What that needs, and what nothing at this point in the flow supplies, is a
domestic-vs-not discriminator.

### A recargo invoice is silently understated, and the printed total that proves it was discarded

Measured on a document printing `Total factura: 126,20` over a base of 100,00 and a cuota
of 21,00: extraction recovered `grand_total = Decimal('126.20')` correctly, and the
confirmed invoice persisted `grand_total = 121.00` with `recargo_amount = None`. The 5,20
the supplier repercuted under LIVA art. 161 vanished, with no diagnostic anywhere.

The derivation is not the fault. `build_catalogue_invoice`
(`src/cadrumo/application/invoices/_creation.py:94`) computes the total as base plus a
registry-resolved cuota and never reads the draft's `grand_total` or `iva_amount`, which is
precisely what the regulated-number discipline requires. The fault is that the disagreement
between printed and derived totals was thrown away. The governing constraint anticipated
this exact situation and mandated the opposite: where the invoice-printed figure disagrees
with the registry-derived one, raise a non-blocking advisory and never overwrite the derived
value; and, naming the temptation directly, an invoice printing "Base 100, IVA 21" is the
most tempting place to break the rule, so the printed figure is an advisory cross-check
only.

The same discarded figure is the only available signal for two further silent
under-declarations on this path. `_resolve_iva_rate_slot(None)` resolves to
`IvaRate.EXEMPT` (`src/cadrumo/application/invoices/_creation.py:74`), so a rate the reader
could not recover mints a zero-cuota invoice whose printed total still shows the cuota that
was charged. A misread base propagates into the derived total the same way. All three are
detectable at zero cost, because the derived total is arithmetically fixed at base plus
cuota: anything the document prints beyond that is either a component the record cannot
hold or a figure it got wrong. That arithmetic is also why one check suffices -- a second
check on the cuota would fire only where the total check already fires.

Note what an advisory does and does not achieve. It makes the loss VISIBLE. It does not
make the recargo capturable: the confirm path still has nowhere to put it.

### The reader cannot identify the counterparty on an issued invoice

`_find_supplier_tax_id` (`src/cadrumo/application/ledger/_evidence_draft.py:256`) returns
the first checksum-valid Spanish tax id in document order, with no label anchoring -- no
attempt to locate "Cliente:", "Destinatario:", "Facturar a:" or "Emisor:". The vision prompt
(`src/cadrumo/application/ledger/_evidence_draft_vision.py:76`) is a module-level constant
taking no direction argument, and instructs the model to return the supplier's NIF/NIE/CIF
exactly as printed. `confirm_invoice_draft_from_evidence` never passes its `kind` down to
extraction, so direction is structurally unavailable to the reader even though the caller
holds it.

On a received invoice the first-match heuristic lands on the supplier, because that is where
the letterhead sits -- correct by accident of layout rather than by logic. On an issued
invoice the issuer IS the filer, so the same scan returns the filer's own identifier, and
the vision prompt asks for it explicitly.

Before the guard landed in commit `6d49d3a2aa`, that produced two failure modes and no
correct path between them. An operator omitting `--counterparty-nif` had their own tax id
silently recorded as the counterparty; nothing objected, because a filer's own NIF is a
checksum-valid Spanish tax id and the identity validator only asks whether the value is
well-formed. An operator who correctly supplied the customer's NIF had the confirm REFUSED
by `_agreed_counterparty_tax_id` (same file, line 491), whose message told them to re-read a
document they had read correctly.

The consequence is not confined to the local record. Counterparty totals on Modelo 347 and
Modelo 349 are informativas AEAT reconciles against what the counterparty themselves
declared, so a fabricated counterparty identity is checked from the outside and the
taxpayer's first signal is a discrepancy notice.

The purchase shaping runs through the surrounding surface as well: the evidence record
carries no direction field and excludes one from its id derivation
(`src/cadrumo/application/ledger/_evidence.py:123`), its counterparty slot is named
`supplier`, the `evidence extract` verb has no `--kind` option, and the review hint the CLI
prints after an extract hardcodes `--kind received`
(`src/cadrumo/entrypoints/cli/_ledger_evidence_cli.py:322`). No issued-direction test
existed for this path before three were added with the guard.

One premise worth correcting for whoever reads this next: the `iva repercutido` alternative
in `_IVA_AMOUNT_LABEL_RE` is NOT evidence of purchase shaping. It is output-VAT vocabulary
printed from the issuer's perspective, so it appears on documents in both directions. The
amount, date, number and currency heuristics are direction-agnostic. The purchase shaping
that matters is concentrated in counterparty identification.

### The regulated-number constraint has a gap on the standalone-invoice path

`_VisionExtractedFields` (`src/cadrumo/application/ledger/_evidence_draft_vision.py:98`)
declares `taxable_base`, `iva_rate` and `iva_amount` as model-emitted fields. The governing
constraint states that the response schema must make it structurally impossible for the
model to emit those three, and adds that evidence reading does not relax this.

What that costs is not uniform, and the distinction matters for whoever acts on it:

- `iva_amount` and `grand_total` are emitted but discarded; the cuota is derived from the
  registry. Compliant in effect.
- `iva_rate` arrives as a free number but is consumed as a closed-slot selection --
  `_resolve_iva_rate_slot` refuses anything outside the taxonomy. That is selection from a
  closed list, which the constraint permits.
- `taxable_base` is emitted by the model and persisted verbatim.

The last one has a complication that makes it a genuine gap rather than a violation to
patch. `confirm_invoice_draft_from_evidence` mints a STANDALONE catalogue invoice with no
linked transaction, so there is no gross from which a base could be derived. The constraint
was written for transaction saturation, where the base is the gross divided by one plus the
rate and the printed figure is genuinely redundant. Read literally against a path that has
no gross, it forbids standalone invoice creation entirely.

Three readings are available and the evidence does not settle between them: require the
confirm to be transaction-linked so a gross exists; amend the constraint to permit a
transcribed base on the standalone path with the printed-total cross-check as the
compensating control; or require an explicit operator-supplied base and demote the extracted
value to advisory.

### Three classifiers have shipped with no production consumer

This surfaced often enough while tracing the above to be worth recording as a pattern rather
than as separate incidents:

- the invoice decomposition contract, dormant until `e173f8e493` wired the income path, with
  the expense and OSS paths still unchecked;
- `route_invoice_retenciones`, dead while its plan step was marked done;
- `simplificada_requires_tax_id_for_domestic_issuer`
  (`src/cadrumo/application/invoices/_issuer_establishment.py`), landed in commit
  `b721701389` and exported through the package facade with no caller within the hour.

Three, not four. `classify_invoice_line_for_iva` was counted here in an earlier draft and
does not belong: it has a production consumer, as recorded above. The correction is kept
visible rather than silently removed, because a pattern claim gets less scrutiny with each
instance added to it -- the fourth instance was the least verified and the only wrong one,
which is the failure mode of arguing by accumulation.

A fifth is the mirror shape rather than another instance: `SELF_SUPPLY_ART_9_1_D`
(`src/cadrumo/core/_prorrata_exclusions.py:54`) documents itself as auto-derived from the
IVA category, against an `IvaCategory` member that does not exist -- a consumer wired to an
absent producer. A check keyed on "exported with no caller" would not catch it.

What the four share is mechanical rather than cultural. Each is a correct, legally grounded
predicate built as a plan-step deliverable and verified by its own unit tests. Those tests
pass whether or not anything calls the predicate, so the step closes green with the enrolment
missing. The decomposition contract shows the compounding cost: it stayed dormant long enough
that its absence became invisible, and the guard that eventually consumed it then degraded
every domestic invoice.

### What was not investigated

The expense and OSS aggregation paths were not checked for decomposition-contract enrolment;
only the income path is known to consume it. No vision model was executed -- the claim that a
model obeying the prompt returns the filer's own identifier on an issued invoice follows from
the prompt text and Spanish invoice layout, though the text-layer equivalent WAS measured.
`BusinessOperationInvoice` was not examined here; a concurrent review reports it carries no
identity validator at all, which would make it a further site of the same totals invariant.
Autoconsumo (LIVA art. 9) was checked only far enough to establish that no `IvaCategory`
member represents it.

## Sources

- `src/cadrumo/application/ledger/_evidence_draft.py:192` -- `InvoiceDraft` field set
- `src/cadrumo/application/ledger/_evidence_draft.py:256` -- unanchored tax-id first-match
- `src/cadrumo/application/ledger/_evidence_draft.py:491` -- `_agreed_counterparty_tax_id`
- `src/cadrumo/application/ledger/_evidence_draft_vision.py:76` -- direction-free prompt
- `src/cadrumo/application/ledger/_evidence_draft_vision.py:98` -- `_VisionExtractedFields`
- `src/cadrumo/application/ledger/_evidence.py:123` -- evidence record without direction
- `src/cadrumo/application/invoices/_creation.py:74` -- `_resolve_iva_rate_slot`
- `src/cadrumo/application/invoices/_creation.py:94` -- `build_catalogue_invoice`
- `src/cadrumo/application/invoices/_issuer_establishment.py` -- unconsumed predicate
- `src/cadrumo/domain/invoices/_decomposition.py:1` -- decomposition contract rationale
- `src/cadrumo/domain/iva/_invoice_classification.py:78` -- domestic-only rate mapping
- `src/cadrumo/domain/iva/_invoice_classification.py:158` -- `classify_invoice_line_for_iva`
- `src/cadrumo/domain/iva/_invoice_classification.py:221` -- `invoice_line_to_iva_observation`
- `src/cadrumo/application/aggregation/_modelo_bindings.py:1097` -- its production caller
- `src/cadrumo/core/_prorrata_exclusions.py:54` -- `SELF_SUPPLY_ART_9_1_D`
- `src/cadrumo/entrypoints/cli/_ledger_business_invoice_cli.py:132` -- sole category assigner
- `src/cadrumo/entrypoints/cli/_ledger_evidence_cli.py:322` -- hardcoded `--kind received`
- commit `bf2a0c880a` -- recargo joins the totals identity
- commit `e173f8e493` -- income-path coherence guard
- commit `1751ce04cf` -- operation date, suplido, class, series, rectificativa
- commit `b721701389` -- issuer-establishment predicate
- commit `6d49d3a2aa` -- self-counterparty guard
- LIVA art. 161 (recargo de equivalencia); LIVA art. 9 (autoconsumo); RD 1619/2012 art. 6.1.d

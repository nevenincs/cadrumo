---
tags:
  - '#adr'
  - '#stray-concept-sweep'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:be6f6fe0def6631a6a3c750a7c79b3fb263be0aa6d4d6e3a2475ce6c42295e6f'
related:
  - '[[2026-08-07-stray-concept-sweep-audit]]'
---
# `stray-concept-sweep` adr: `representing a purchase refund on the IVA ledger axis` | (**status:** `proposed`)

## Context

A stray-concept sweep found three byte-identical private copies of
`_invoice_kind_for`, at `application/aggregation/_iva_ledger.py:1518`,
`application/aggregation/_evidence_advisory.py:134` and
`application/modelo/_ledger_evidence_gate.py:98`. Each maps a bank
`TransactionDirection` onto `InvoiceKind` on direction alone:

```python
if direction is TransactionDirection.INCOMING:
    return InvoiceKind.ISSUED
if direction is TransactionDirection.OUTGOING:
    return InvoiceKind.RECEIVED
return None
```

The reported defect is that a supplier refund or credit note on a returned
purchase is an `INCOMING` bank movement carrying a populated
`purchase_invoice_evidence_id`, so it resolves to `ISSUED`, then through
`derive_flow_for_classification` to `REPERCUTIDO` — output IVA added to cuota
devengada where the correct treatment corrects input IVA.

Every element of that was confirmed at HEAD. The three copies are identical.
`purchase_invoice_evidence_id` is a plain `str | None` on `Transaction`
(`domain/transactions/_models.py:775`) carrying no cross-field validator against
direction, and it is operator-settable on any row through
`aeat app ledger add --purchase-invoice-evidence-id` and the lifecycle attach
verb, so the combination is reachable rather than theoretical. The IVA path
reads only `transaction.direction`: `purchase_invoice_evidence_id` appears
nowhere in `_iva_ledger.py`.

The originating register proposed extracting one canonical
`invoice_kind_for_ledger_row(direction, purchase_invoice_evidence_id, ...)`
beside `InvoiceKind`, propagating refund detection to all three call sites, and
described this as additive and self-contained.

**That fix cannot produce a correct figure, and the reason is the decision this
ADR exists to take.**

`InvoiceKind` is a two-member axis — `ISSUED` / `RECEIVED` — carrying no sign.
Ledger amounts are absolute magnitudes by standing rule
(`ledger-amount-is-absolute-direction-is-authority`): direction is the sole flow
authority and no amount may encode reversal in its sign. A refund routed to
`RECEIVED` therefore lands on the soportado axis as a *positive* contribution
and **increases deducible input IVA**. That trades an over-declaration of output
IVA for an over-declaration of deductible input IVA. It is not obviously the
lesser error; deducting IVA that was refunded is the shape a comprobación
penalises.

The in-tree pattern the register cites as the antidote confirms this reading
rather than contradicting it. `_renta_direction_for`
(`application/aggregation/_renta_ledger.py:680`) does consume the same signal,
but it does not return the opposite direction — it returns a *third* member,
`RentaExpenseDirection.REFUND`, and `RentaDeductibleExpenseFact.sign`
(`domain/renta/_ledger_expenses.py:194`) resolves that member to `-1`. Renta
models a refund as a negative contribution on the expense axis. It is a
three-member signed axis; `InvoiceKind` is a two-member unsigned one. The
pattern was not "left unpropagated" — it has no counterpart to propagate into.

The one place the IVA side can express a signed reversal is
`IvaLedgerCandidate` with `IvaLedgerInputKind.ADJUSTMENT`, whose own docstring
states that such rows "may carry negative bases or cuotas because rectification
and regularisation entries reverse or correct prior operations. The registry
consumes the resulting signed observation" (`_iva_ledger.py:254-266`). That
model has **zero production producers**: every one of its ten construction sites
is in `application/aggregation/tests/test_iva_ledger.py`, and `ADJUSTMENT` is
set in exactly one of them. So the sanctioned representation for a correcting
entry exists, is exported, and nothing in production reaches it — dormant
capacity of the kind `no-dormant-source-resolvers` targets — while the
transaction-derived path that every real bank row travels has no signed
representation at all.

The decision is therefore not "which value should `_invoice_kind_for` return".
No return value of that function is correct. The decision is **how a correcting
entry is represented on the IVA ledger axis at all**, and that is a modelling
choice with legal consequences (LIVA art. 80 modificación de la base imponible;
art. 89 rectificación de cuotas repercutidas), not an extraction.

## Decision

Deferred pending owner adjudication. Three options are laid out; this ADR
records the analysis and the recommended interim, and is deliberately not
self-accepting, because each option changes what a filed cuota contains.

**Option A — refuse, do not guess (recommended interim).** Make the IVA
aggregation refuse an `INCOMING` transaction carrying a populated
`purchase_invoice_evidence_id`, through the existing
`IvaLedgerAggregationIssue` channel that already carries
`UNSUPPORTED_DIRECTION`, with a reason naming the row as a purchase correction
the IVA aggregation cannot yet route and pointing at the manual adjustment path.
This converts a silent wrong figure into a visible refusal, satisfies
`no-silent-under-declaration`, and pre-empts none of the representational
choice below. It is strictly safer than today: those rows currently produce a
wrong number rather than no number.

**Option B — wire `ADJUSTMENT` (the principled destination).** Give the
transaction-derived path a producer for `IvaLedgerCandidate` /
`IvaLedgerInputKind.ADJUSTMENT`, so a refund becomes a signed correcting
observation on the soportado axis. This is the representation the model was
built for and retires the dormancy in the same change. It is the larger piece of
work: it requires deciding how a refund's base and cuota are derived from the
linked purchase evidence, and how a partial refund apportions.

**Option C — a signed IVA disposition mirroring renta.** Introduce an explicit
direction/disposition axis on the IVA ledger observation carrying a `sign`, as
`RentaExpenseDirection` does. This duplicates in the IVA domain a mechanism
`ADJUSTMENT` already provides and is recorded only to be rejected explicitly, so
it is not rediscovered as an unexplored option.

Option B is the destination; Option A is what should land first and is
independently justified.

**In every option the three duplicated copies of `_invoice_kind_for` are
consolidated to one canonical helper.** That consolidation is correct
regardless — three private copies of one mapping is drift by construction — but
it must not be mistaken for the fix. Consolidating them and adding refund
detection would produce one canonical *wrong* answer in place of three
duplicated ones.

## Consequences

Until one of these lands, an `INCOMING` row carrying
`purchase_invoice_evidence_id` is declared as output IVA and inflates cuota
devengada, and the soportado correction is silently omitted. The exposure is
bounded by how often that combination is created: it requires an operator to
attach purchase evidence to an incoming movement, which the CLI permits and
nothing warns against.

Any accepted option needs a test that is red without it. A test asserting the
current mapping's *output* would not do: the defect is that the axis cannot
express the answer, so the test must assert the aggregated cuota devengada for a
refund row against a figure grounded in an AEAT worked example under
`no-tautological-calculation-tests`, not against a hand-computed application of
the same formula.

`retired-enum-members-need-consumer-reconciliation` is not triggered by Option A
or B: neither retires an enum member. Option B adds a production producer for an
existing member.

## Related

Verified at HEAD `dbe38493c1`. Disposition register:
`2026-08-07-stray-concept-sweep-audit`.

---
tags:
  - '#audit'
  - '#stray-concept-sweep'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:149a5a5de9a918469194dd008e4d6e3810848c72cc8ce5ebfd4f95642063e688'
related: []
---
# `stray-concept-sweep` audit: disposition at HEAD

Disposition pass over a five-concept stray-concept sweep (IVA treatment,
prorrata, expense deductibility, invoice kind/direction, invoice-shaped
records; 72 semantic queries across five lanes). The sweep was authored against
HEAD `f27ccd4cb8`; this pass ran at `dbe38493c1`, **180 commits later**, and
every finding was re-verified before disposition. The sweep directory lived
outside the git tree; this document is its surviving record.

Method: `vaultspec-rag` semantic search by meaning first, then `rg` and full
reads at HEAD, and — for the two findings whose mechanism was contested — a
running probe rather than a reading. Two findings changed materially on
contact, and in both cases only the executed measurement caught it.

## Summary of dispositions

| # | Finding | Disposition |
|---|---|---|
| L1 | Purchase refund declared as output IVA | **Needs an ADR** — authored |
| L2 | `--irpf-category` unvalidated at every layer | **Route** — ledger surface |
| L3 | `CounterpartObservation` drops invoice number and cuota | **Route** — invoice campaign |
| L4 | `operation_kind` untyped on the M347/M349 boundary | **Fixed** — `d6a28e8262` |
| L5 | Category membership enforced only in Typer | **Route** — own campaign; naming half fixed |
| P1 | M349 gate justified on a refuted premise | **Already closed by a peer** |
| P2 | Prorrata docstring names the wrong rounding mode | **Fixed** — `20e428cec0` |
| P3 | `domain/categories` claims a parity that does not exist | **Already closed by a peer** |
| D1 | Test oracle inherits banker's rounding | **Fixed** — `20e428cec0` |
| D2 | `_NUMERIC_IVA_RATE_SLOTS` re-lists an enum-derived set | **Not actioned** — reason recorded |
| D3 | Two rate-tier → category tables | **Not actioned** — reason recorded |
| D4 | `IvaLedgerCandidate` / `ADJUSTMENT` dormant | **Folded into the L1 ADR** |

## Findings whose severity or mechanism changed on contact

### L1 — the proposed fix cannot produce a correct figure

The defect is real and reachable: three byte-identical copies of
`_invoice_kind_for` map direction alone, `purchase_invoice_evidence_id` carries
no cross-field validator against direction, and the CLI sets it on any row. All
confirmed at HEAD.

What changed is the *fix*. The register proposed extracting one canonical
`invoice_kind_for_ledger_row(...)` returning an `InvoiceKind`, called this
additive and self-contained, and pointed at `_renta_direction_for` as the
pattern to propagate. `InvoiceKind` is a two-member unsigned axis, and ledger
amounts are absolute by standing rule, so routing a refund to `RECEIVED` puts it
on the soportado axis as a *positive* contribution and inflates deducible input
IVA — trading one wrong figure for another. The renta pattern does not
transfer: `_renta_direction_for` returns a *third* member, `REFUND`, which
`RentaDeductibleExpenseFact.sign` resolves to `-1`. It is a signed
three-member axis with no counterpart on the IVA side.

The only signed representation available on the IVA side is
`IvaLedgerInputKind.ADJUSTMENT`, which has zero production producers. So the
question is not what `_invoice_kind_for` should return — no return value is
correct — but how a correcting entry is represented at all. That is a modelling
decision with legal consequences (LIVA arts. 80, 89), which is why this became
an ADR rather than a fix. The register's own closing note ("wiring `ADJUSTMENT`
is the better answer, and it should be decided together with L1") was right and
is in tension with its own rehoming table, which proposed the shallow
extraction; the shallow one is the wrong half of that tension.

The three duplicated copies should still be consolidated under any option, but
consolidating them with refund detection would produce one canonical *wrong*
answer in place of three duplicated ones.

### L4 — the mechanism is a silent drop, not a split row, and the named fix is wrong

The register described a non-canonical `operation_kind` as splitting one
counterparty into two rollup rows. Measured, it does not. The aggregator routes
each observation by testing this field against the requested modelo's clave set
(`filter_observations_for_modelo`), so a token in **neither** the 347 nor the
349 vocabulary matches neither pass and is **dropped entirely**, while the
aggregation's totals still reconcile because they are summed from the surviving
rollups.

Probed directly, a €10,000 above-threshold observation with `operation_kind`
`"Entregas_Y_Prestaciones"` was admitted at the operator boundary and produced
a Modelo 347 preview reporting `total_counterparties=0` and
`total_taxable_base=0`, with no error and no notice. That is a silent
under-declaration on an informativa a human files, and it is worse than the
split row the register described. Severity up.

The register's proposed fix — typing the field as `IntracomOperationType` — is
also wrong, and wrong in the way the register's own Shape C warns against.
`IntracomOperationType` is the single-letter clave vocabulary carried by
*invoice* records and covers M349 only; `CounterpartObservation.operation_kind`
carries the descriptive Spanish token vocabulary (`entregas_y_prestaciones`,
`entrega_intracomunitaria_bienes`) spanning **both** M347 and M349. Typing it to
`IntracomOperationType` would break the M347 axis outright. The register said
"do not force that synthesis" about `SpendingCategory`/`IvaCategory` and then
forced a structurally identical one here.

Fixed by refusing, at the operator JSON boundary, a token in neither
vocabulary — validated against the union of `OperationKind347` and
`OperationKind349`, both already imported in the module and both already the
source the routing catalogue derives from. Cross-modelo filtering is
deliberately left intact: a canonical 349 clave handed to the 347 pass must
still be skipped rather than refused, and a test pins both halves. The fix sits
inside the file's existing `TestObservationBoundaryAuthorities` class, which had
already hardened `accrued_on` and `operation_period` at this same boundary with
a positive control and simply had not covered this field — every test in it was
already passing canonical enum values for `operation_kind` while the model typed
it as a bare string.

### P1 and P3 — already closed by a peer, between the sweep and this pass

Both were verified false-at-HEAD, in the sense that the defect no longer exists.

P1 was the register's flagship ADR candidate: a docstring justifying a
deliberately weakened M349 gate on the claim that intra-community *services* map
to no `IvaCategory` member. Commit `8c6d7757fc` ("re-ground the M349 absence
guard on a premise that holds", plan step P01.S34) not only corrected the
docstring but **re-derived the justification** on a premise that does hold —
that `_intracommunity_clave` consults an explicit `operation_type` first and
returns without reading `iva_category`, so absence genuinely does not mean
inexpressible — and left the refuted claim in place as an explicitly labelled
correction. That is precisely the ADR-level re-derivation the register asked
for, already done, by the campaign that owns the file.

P3 was closed by `f9305acd3a`, which renamed `InvoiceLine.category_id` to
`spending_category_id` and rewrote the `domain/categories` entry to state the
opposite of the old claim: the slot "is NOT typed to this taxonomy and no
aggregation consumer reads it today — an earlier form of this entry claimed
both, and a reader who trusted it would look for a coupling that does not
exist."

Recorded because the register's own instruction was that a `path:line` citation
is evidence of specificity and never of currency. Both citations were accurate
when written and stale when read.

## Findings routed rather than fixed

**L3 — `CounterpartObservation` drops `invoice_number` and the explicit cuota.**
Confirmed at HEAD: the model carries `taxable_base` and `invoice_total` but no
`invoice_number` and no `iva_rate`/`iva_amount`, so cuota exists only implicitly
as the difference, which absorbs any recargo de equivalencia component
unguarded. Routed to `invoice-canonical-structure` rather than fixed here: that
campaign is mid-decision on the *same* boundary — its plan works through
`CounterpartAggregationObservation.source_kind` and the taxonomy mismatch
between `CounterpartSourceKind` and the invoice binding family — and widening
this model underneath an in-flight taxonomy decision would collide. Belongs as a
Step in that plan, downstream of the source-kind decision it already carries.

**L2 — `--irpf-category` has no validator at any layer.** Confirmed: no
`_validate_irpf_category` exists anywhere in the tree, and
`ledger_irpf_category()` resolves an unrecognised token to `None`, meaning no
withholding treatment. Not fixed here because the honest fix is not a lone
membership check: `ledger_irpf_category()` takes a `direction` and returns
`None` for three distinct situations (no token, unknown token, token whose
descriptor does not admit this direction), so a CLI-boundary check must
distinguish "you mistyped" from "this category does not apply to this
direction" or it will refuse legitimate rows. It also needs a refusal message in
four locale catalogues through the `cadrumo.locales` CLI. That is a scoped piece
of work on the ledger surface, not a drive-by. Belongs with L5.

**L5 — category membership enforced only in Typer callbacks.** Confirmed, and
the architectural point stands: the MCP and agent-harness surfaces construct
application commands directly and walk around a Typer gate, and this product's
primary operator is an autonomous agent. Moving membership onto the domain
models touches the ledger surface broadly and warrants its own campaign.

The cheapest half was fixed here. The register reported four functions named
`_validate_category_id` doing two different things; at HEAD there are **three**,
the invoices copy having been renamed to `_validate_spending_category_id` by
`f9305acd3a`. The remaining misleading one is on `ClassificationHistoryEntry`
(not `Transaction`, as the register placed it) and is renamed to
`_normalize_category_id` in `20e428cec0`, so the validating name now belongs
only to the two helpers that validate.

## Findings deliberately not actioned

**D2 — `_NUMERIC_IVA_RATE_SLOTS` re-lists `{0,4,10,21}`** at
`application/invoices/_creation.py:62` while `application/review/_edit.py:152`
derives the same set from `numeric_iva_rate_percentages()`. Confirmed, still
agreeing value-for-value, and the divergence trigger is real and named in the
enum's own docstring: `RATE_5`, the transient 2022–2024 rate, deliberately
absent. Not actioned because it sits in `application/invoices/`, inside the
`invoice-canonical-structure` campaign's working set, and because it is drift
with no present error — the class this register is careful to keep separate
from the defects. It should become a Step in that campaign, not a foreign edit
mid-flight.

**D3 — two hand-authored rate-tier → category tables** at
`domain/iva/_invoice_classification.py` and `domain/iva/_classification.py`.
Confirmed, agreeing today. Not actioned for the same reason plus one more: the
narrower of the two is documented as domestic-only, rejects `NOT_SUBJECT` with
an instructive error, and directs non-domestic callers elsewhere — a
correctly-scoped helper rather than drift. `domain/iva/_classification.py` also
received a peer commit during this pass (`7d211540b0`).

The reference-good pattern for all three, when they are actioned, is
`CUOTA_LESS_M303_IVA_CATEGORIES` in `domain/iva/_schema.py`: one canonical
frozenset guarded by both a runtime assertion and a dedicated parity test.

## What was confirmed still clean

The register's clean list was spot-checked rather than re-derived, and nothing
contradicted it. Specifically re-confirmed: `IvaLedgerCandidate` still has zero
production producers (all ten construction sites in
`test_iva_ledger.py`); no fifth declaration of the issued/received binary; the
`accrued_on` date bound the register had corrected is indeed validated through
`IsoDateString`, and its boundary tests exist with a positive control.

## Live disagreements between a stray implementation and its canonical source

Reported separately because these are defects rather than refactors. Exactly
one was found, and it is L4: `operation_kind` was admitted by a rule
(non-blankness) strictly weaker than the rule its only consumer applies
(membership in the modelo's clave set), and the gap between the two was a silent
drop rather than an error. Every other duplicate mapping examined agreed with
its canonical source value-for-value at HEAD.

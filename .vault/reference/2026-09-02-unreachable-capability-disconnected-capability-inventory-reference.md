---
tags:
  - '#reference'
  - '#unreachable-capability'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:ba0e75f841aa0c1bbf5c9f5048e29ae0f32c35e961c18c69e88f6e2e84d0dfe2'
related:
  - "[[2026-09-02-unreachable-capability-research]]"
---

# `unreachable-capability` reference: `capability built but unreachable from the CLI`

## Summary

An inventory of capability that is built, tested, and shipped inside the wheel,
and that no console-script entrypoint can reach. It is not a dead-code list:
the superseded and duplicated surfaces were retired earlier and are gone. What
remains is, in the main, work that functions and was never connected.

The reachability facts come from `python -m dev.audit.unreachable_code`, which
walks the import graph from the declared console scripts, the shipped
`__main__.py` surfaces, and the sibling workspace distribution. At the time of
writing it reports 49 findings spanning 86 modules.

Each entry answers five questions: what the capability is in tax terms, how
complete it is, why it is not connected, what it adds to the filing product,
and the smallest wiring that would reach it. The third answer uses a fixed
vocabulary — bug, oversight, explicit decision, unfinished, sequenced — and an
explicit decision requires a citation, because an absence of callers is
evidence of nothing.

One cross-cutting fact belongs here rather than in any single entry. Every
`consumer` declared across the shipped registry data was checked against the
reachable module set, and exactly one names a module no entrypoint can reach:
the Modelo 100 revision 2025 cross-reference row for the Renta WEB Open portal
surface. That is the only case where registry data declares a consumer that
does not consume.

## The registry axis

A binding declaration and the code that resolves it are two halves that can
drift apart independently, so the registry was checked from both directions.

**Declared consumers that cannot run.** Every `consumer` string across the
shipped registry tree was resolved against the reachable module set. Exactly
one names a module no entrypoint can reach: the Modelo 100 revision 2025
cross-reference row naming the Renta WEB Open portal surface. Registry data
therefore asserts a consumer relationship that cannot execute, and it is the
only such row.

**Resolvers with nothing to resolve.** The canonical `BindingSourceKind`
vocabulary carries 33 members. Thirty-two source families appear across the
9,020 binding declarations in shipped data. Comparing the two sets leaves five
enum members that no registry row anywhere declares:

- `borrador`
- `iva_wallet_decision`
- `ledger_transaction`
- `purchase_invoice_evidence`
- `withholding296`

None is a reserved placeholder. Each is referenced by real resolver and
validator code outside tests, between six and nineteen sites apiece, across
`application/aggregation`, `application/calculations`, `application/review` and
`application/ledger`. So the mechanism can resolve five source families that no
declaration ever asks for.

The `borrador` entry is the sharpest, because its adapter is independently on
the unreachable list: `adapters/inbound/borrador/` parses the Modelo 100 draft
and no entrypoint reaches it, while the binding family that would carry its
values into casillas is declared by no revision. Both halves of that feature
are disconnected, in different ways, which is why neither shows up as a broken
reference anywhere.

A caution for anyone repeating this measurement. A first pass over `source =`
strings also reported `ley_irpf`, `manual_renta`, `reglamento_irpf` and
`aeat_help` as undeclared families. They are not binding sources at all: they
are legal-citation sources on the category proportionality declarations, with
their own enum in `domain/categories/proportionality.py`. Two unrelated
declaration kinds share the `source` key, and conflating them invents four
defects that do not exist.

## Entries

### `domain/fincas/` with `adapters/persistence/profile/fincas.py`

**What it is.** Spanish rental-property income for the IRPF annual return: the
computation an operator needs to declare what a let property earned. Gross
rent per contract, deductible expenses under LIRPF article 23.1 with the
carry-forward the article requires, the article 23.1.f amortisation, the
article 23.2 reducción tier resolution for residential letting, and the
article 85 imputation for property that was not let.

**How complete.** Eleven domain modules and a five-repository persistence
adapter, around 1,800 lines of implementation against roughly 1,400 lines of
tests, all passing. It is registry-grounded rather than hard-coded: sixty
rental parameters ship across the Modelo 100 revisions carrying `legal_refs`
to LIRPF article 23, with the amortisation rate additionally citing RIRPF
article 14, and several carrying source citations whose required text is
verified against the bundled corpus.

The persistence half needs no work at all. The five `rental_*` tables are
declared on the same SQLAlchemy base whose `metadata.create_all` runs at
`adapters/persistence/storage/sql/engine.py`, so every profile database that
exists today already carries them, empty.

Verified against the bundled AEAT manual rather than assumed: all four
reduction tier rates match, both tenant age bounds match, the rent-reduction
threshold matches, and the proportional co-tenant rule is implemented with the
governing BOE sentence quoted at the implementation site in
`domain/fincas/tier_resolver.py`.

**Why not connected.** SEQUENCED, with a real modelling gap behind it. The
source-connectivity census row `fincas.annual-aggregates` is
`grounding_blocked`, and the plan that owns it hard-sequences fincas behind
amortization, whose own promotion step is still open. The row's stated blocker
and the code's stated blocker disagree — `domain/fincas/source_readiness.py`
reports a persistence gap, which is the closed meaning of a different
disposition — and that disagreement is unresolved.

The genuine gap is narrower than either: the `Finca` record carries no
ownership or usufruct share, so it assumes full title, while the manual
requires the owning contribuyente and both percentages as per-property facts.

**What it adds.** Rental income is one of the most common IRPF situations for
an individual filer, and the article 23.2 reduction is worth between 50 and 90
per cent of net income depending on tier, which is a large sum decided by
conditions most filers get wrong by hand. The engine already resolves those
tiers correctly against the manual. Connected, it turns a return that a
landlord cannot presently prepare in this product into one they can.

This is the largest single block of finished, legally grounded capability in
the inventory.

**Wiring needed.** Three things in order, none of them small. Route the
aggregates through the encrypted calculation-revision boundary so readiness can
return true. Add the ownership and usufruct fields the manual specifies. Decide
the destination casilla mapping, which the bundled manual can settle: its
chapter 4 names the destination casillas individually and fixes the grain with
a worked example of one property across two successive tenancies, income per
contract inside a per-property per-year envelope. Only then a CLI subject over
the repositories that already exist.

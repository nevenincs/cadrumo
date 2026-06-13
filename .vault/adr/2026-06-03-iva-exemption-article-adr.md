---
tags:
  - '#adr'
  - '#iva-exemption-article'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-06-03-iva-exemption-article-research]]"
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# `iva-exemption-article` adr: `IvaExemptionArticle discriminator on Transaction` | (**status:** `accepted`)

## Problem Statement

Plan Step W09.P41.S354 (R9-TOMAS-HIGH) blocks Modelo 303 casilla 61
(operaciones exentas interiores con derecho a deducción) reporting
because `IvaCategory.DOMESTIC_EXEMPT` collapses every Ley 37/1992
Art. 20 sub-article into a single bucket. Art. 20.Uno.26 (artistas
plena con prorrata) preserves the deduction right; Art. 20.Uno.8
(enseñanza) does not. Without a discriminator the calculation chain
cannot route artista operations to casilla 61, and the persona
reports silently understated recoverable IVA.

## Considerations

The research doc maps three design options. This ADR locks Option A
(additive discriminator field) for the reasons named there: the
existing IvaCategory consumers see no change (the discriminator is
optional with `None` default), the casilla-61 routing reads cleanly
from the discriminator value via a tiny mapping, and the
classification rules extend incrementally as each sub-article's
transaction-shape heuristic stabilises.

The closed enum membership is scoped here to the sub-articles whose
deduction-right or M303-routing semantics differ. The MVP set is
`ART_20_UNO_8` (enseñanza), `ART_20_UNO_14` (sanitarios),
`ART_20_UNO_26` (artistas plena con prorrata), and `ART_20_OTHER`
(catch-all for sub-articles whose semantics do not yet warrant a
dedicated slot). New slots open per follow-up Step as their routing
demands surface.

The discriminator's classification path is inference-where-possible,
operator-declared-where-not. Artistic services with a clear
artist-counterparty marker can be auto-classified as `ART_20_UNO_26`;
sanitary services with a healthcare-provider counterparty marker can
be auto-classified as `ART_20_UNO_14`. Sub-articles that depend on
context not present on the transaction (e.g. the customer's
prorrata status) remain `None` until the operator declares them via
an existing transaction-edit verb.

## Constraints

The discriminator MUST NOT be settable on a transaction whose
classified `category` is not `DOMESTIC_EXEMPT`. A
model-validator on the Transaction record rejects the inconsistency
at construction time so a stamped discriminator is always
co-consistent with the category.

The casilla-61 routing on M303 is registry-authored, not
hard-coded. The Modelo 303 revision binds casilla 61 to a selector
that filters transactions with `category=DOMESTIC_EXEMPT` AND
`exemption_article ∈ {ART_20_UNO_26, ...deducible-right set...}`,
keeping the regulatory mapping in the authoring layer per
`aeat-schema-central-config`.

The legal_refs on the new closed enum (each member cites its Ley
37/1992 article) MUST be defined in the legal catalogue per
`registry-calculation-legal-grounding`. The catalogue entries for
each Art. 20.Uno.N sub-article cross-reference the BOE Ley 37/1992
corpus.

## Implementation

Land in one atomic explicit-path commit per the relocation-atomicity
rule:

1. New closed enum `IvaExemptionArticle` under
   `src/aeat/domain/iva/_schema.py` next to `IvaCategory`. StrEnum
   with MVP members named above; docstring cites Ley 37/1992 art-20
   per the registry-calculation-legal-grounding rule.
2. New optional `exemption_article: IvaExemptionArticle | None`
   field on the Transaction model. Model-validator rejects
   `exemption_article != None AND category != DOMESTIC_EXEMPT`.
3. Classification rules in `src/aeat/domain/iva/_classification.py`
   gain auto-classification heuristics for the ART_20_UNO_8 / 14 /
   26 cases that can be inferred from transaction shape. Heuristics
   that fail leave the field `None` rather than guessing.
4. Roundtrip + service-contract tests on the Transaction model and
   the classification rules. Anti-tautology proof per
   `aeat-roundtrip-discipline`: an `exemption_article` stamp on a
   non-DOMESTIC_EXEMPT transaction fails the validator.

Casilla-61 routing (S355) opens as a separate Step gated on this
ADR.

## Rationale

Option A keeps the cross-cutting `IvaCategory` enum stable —
critical because the enum is consumed across the classification
chain, the invoice classification, the calculation registry, the
M303 / M390 routing, and operator-facing display. Splitting the
DOMESTIC_EXEMPT slot into per-article variants (Option B from the
research doc) would force every existing call site into a switch
statement over the sub-articles. The additive discriminator routes
the same information without that sweep.

The closed-enum membership stays small for the MVP because the
deduction-right routing on M303 only distinguishes deducible-vs-not
at this layer. Sub-articles with finer regulatory implications open
new enum slots when their routing demands materialise.

## Consequences

The closed enum + Transaction-field landing is one focused commit;
the classification heuristic extensions are per-heuristic follow-ups
that ride the same enum slot they fill. M303 casilla 61 (S355)
opens as the immediate consumer once the discriminator exists.

A Transaction stamped with the discriminator carries enough
information for the casilla-61 router; a Transaction with
`exemption_article = None` continues to route as today (collapsed
DOMESTIC_EXEMPT). Operator-declared discriminator values land
through the existing transaction-edit verb without a new CLI
surface.

The auto-classification heuristics for ART_20_UNO_8 / 14 / 26 land
case-by-case; each heuristic carries its own test that proves the
positive case auto-stamps and the negative case leaves the field
`None`. A heuristic that cannot be made reliable stays operator-
declared rather than guessing.

## Codification candidates

- **Rule slug:** `discriminator-field-implies-consistent-category`.
  **Rule:** A discriminator field on a domain record (e.g.
  `exemption_article` on Transaction) that only applies when the
  record's parent classification holds a specific value MUST be
  enforced by a model-validator that rejects the inconsistent pair
  at construction time. Optional fields without this guard drift
  into stamped-but-unreachable states that calculation chains then
  silently miss.

  Held until a second such discriminator lands and the pattern
  proves itself across two records.

---
tags:
  - '#adr'
  - '#iva-art-69-dos-services'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:2d347dd98c1ad8e977866ba078c5ad01a6e7cf361239c51318fceb12886ce886'
related:
  - "[[2026-08-12-iva-service-localisation-adr]]"
  - "[[2026-08-12-iva-service-localisation-reference]]"
---

# `iva-art-69-dos-services` adr: `the outbound B2C carve-out is a closed statutory list the operator names` | (**status:** `accepted`)

## Problem Statement

The outbound services fork now taxes every B2C service a mainland issuer bills
outside the Comunidad, because art. 69.Uno.2.º places the supply at the supplier.
Art. 69.Dos excepts a closed list of twelve service kinds from exactly that
paragraph, and the list is not modelled, so its population is over-taxed by
default. That was accepted as a named carry-forward in
`2026-08-12-iva-service-localisation-adr` rather than as a resting place.

This record rules on how to model it, and on one adjacent question that reading
the statute closed rather than opened.

## Considerations

- Over-taxation is the direction the project's own mandate says nothing watches:
  it produces valid output, no refusal and no signal. A named carry-forward
  bounds it; it does not fix it.
- The list is a CLOSED legal vocabulary of twelve lettered items, fixed by
  statute. That is the same shape the citation axis already reads and the
  opposite of inferring a service kind from an invoice's prose.
- Art. 69.Dos states its own limit in the same sentence: the exception does not
  reach a recipient in Canarias, Ceuta or Melilla, though those territories are
  outside the Comunidad.
- The tree already carries a sub-article discriminator of exactly this shape,
  `IvaExemptionArticle` over Ley 37/1992 art. 20.

## Considered options

**A closed enum of the twelve lettered items, declared by the operator.**
Chosen. The statute fixes the vocabulary, the operator states which item applies,
and the application infers nothing from the invoice's words.

**Infer the item from the line descriptions.** Rejected outright. "asesoría"
implies letter d) is a model wearing a lookup table -- confident on the
population it was written against, silently wrong everywhere else. The
supply-nature module refuses this by name and the same refusal governs here.

**Add the items to `TransactionKind`.** Rejected. That axis routes rate tiers and
reverse-charge sub-rules; twelve members that answer a different question would
make every consumer of it read past them.

**Leave the carry-forward standing.** Rejected. It was recorded as a bound on a
known defect, and the axis it said was missing turns out to be twelve enum
members and one predicate.

## Constraints

- The exception is B2C only. Art. 69.Dos excepts from 69.Uno.2.º, which is the
  B2C paragraph, so a declared list item changes nothing on the B2B limb.
- An undeclared item is not evidence of absence. A B2C service whose item nobody
  stated stays taxed here, which is the same fail-toward-declaring direction the
  rest of this axis takes.

## Implementation

A closed `StrEnum` carries the twelve items, each member documented from the
bundled consolidated text it is read out of. The criteria record gains one
optional field for it, defaulting to absent.

The B2C branch then splits in two. A declared item, with a recipient in a third
country, is not realizada en el TAI and classifies not-subject under art. 69.Dos.
Everything else on the B2C limb -- no item declared, or a recipient in Canarias,
Ceuta or Melilla -- stays on the rate-tier branch and is taxed here. The
rate-tier demand follows the same split, so the excepted branch is not asked for
a tier it does not use.

## Rationale

The knockout is that the objection to modelling the list was never about the
list. It was about inference: nothing may decide from an invoice's prose which
lettered item it falls under. An operator-declared closed vocabulary does not
infer, which is why the tree already has one for art. 20 and why the citation
axis is allowed to read article numbers at all.

## Consequences

The over-taxed population shrinks to those B2C services whose item the operator
has not stated, which is a question rather than a silent charge.

**One adjacent claim is RETRACTED rather than carried.** The prior record's
honesty pass flagged electronically supplied services as probably over-taxed by
the subject outcome. Reading the statute says otherwise: art. 70.Uno.4.º locates
e-services, telecommunications and broadcasting at the recipient only when the
recipient is established in the TAI, so it does not reach an outbound supply at
all; art. 70.Dos only ever pulls services INTO the TAI that would otherwise fall
outside the Comunidad, so it can add Spanish taxation and never remove it; and
art. 69.Dos names no e-services item. An outbound B2C e-service to a non-EU
consumer is therefore located in the TAI by art. 69.Uno.2.º and taxed here. The
subject outcome is correct, not a defect to be fixed later.

That retraction is the reason this record exists as its own decision rather than
as an amendment: the earlier note would otherwise stand as an open concern that a
later reader would spend effort re-deriving.

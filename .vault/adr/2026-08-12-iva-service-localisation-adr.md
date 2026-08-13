---
tags:
  - '#adr'
  - '#iva-service-localisation'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:0cfff272789fa585e50e0952484cd22f01a25a8b6338427ed547287c4d914b1d'
related:
  - "[[2026-08-12-iva-service-localisation-reference]]"
---

# `iva-service-localisation` adr: `the services limb is located by the recipient's condition, and grounded at the anchor` | (**status:** `accepted`)

## Problem Statement

The outbound services classification row grants `OPERACION_NO_SUJETA` on the
customer's ESTABLISHMENT alone. LIVA art. 69 does not: it forks on whether the
recipient is an *empresario o profesional que actúe como tal*, and the two limbs
land in opposite places. The row therefore books as not-subject two populations
the law places inside the TAI, and both directions of the error under-declare.
One of them was widened into existence today, by this campaign.

Separately, the same limb cannot be grounded. The statutory-citation vocabulary
that tells a reader whether a supply is of goods or of services omits every
general place-of-supply article, so both SERVICE categories derive nothing from
their own grounding and the operator is asked a question the law has answered.
The grounding gap and the classification defect are the same limb seen from two
sides, and are decided together so the fix to one cannot quietly restate the
other's assumption.

Grounding, provenance and the measured consequences are in
`2026-08-12-iva-service-localisation-reference`.

## Considerations

- Under-declaration is the governed direction: a rule granting not-subject
  without an affirmative fact behind it is the exact shape the project's
  no-silent-under-declaration mandate exists to refuse.
- The fork's input already exists. `IvaInvoiceClassificationCriteria` carries
  `customer_tax_status`, nine sibling rows already read it, and the rule table
  already declares per-row which party facts it consumes.
- Art. 69.Dos's carve-back is EXPRESS about Canarias, Ceuta and Melilla, so no
  judgement is required to know the widened row is wrong there.
- The anchor-scoped corpus read is not a new mechanism: the registry's evidence
  validator resolves `<file>#<anchor>` already, and a shipped gate pins that a
  file-scoped check cannot produce the refusal an anchor-scoped one does.
- Art. 22 is bundled per-article and still uncheckable, for an unrelated reason:
  its opening enumerates operation kinds rather than naming a limb.

## Considered options

**Read the customer's condition on the outbound services row.** Chosen. The fork
the statute draws, on an axis the criteria record already carries.

**Narrow the row back to `THIRD_COUNTRY` and drop the widening.** Rejected. It
fixes the Canarias regression and reintroduces the gap the widening closed, while
leaving the older B2C defect untouched in the third-country population. It trades
one under-declaration for another.

**Split R22 into a B2B row and a B2C row.** Rejected as the primary shape but
adopted in effect: the table's rows are predicates, and two predicates over
disjoint customer-status sets is what "read the condition" means here. What is
rejected is duplicating the territorial chain across them.

**Enumerate the art. 69.Dos list (a-l) as a service-kind vocabulary.** Rejected
for now. `TransactionKind` has one general services member, so the list has no
axis to attach to; asserting the list without one would mean deciding which
lettered item an invoice falls under from its prose, which is the rule-table-as-
model this domain already refuses. The B2C branch therefore resolves to SUBJECT,
which is the safe direction, and the exception is left to the operator.

**Give the citation rows anchors.** Chosen. The alternative -- fetching three
more per-article files -- duplicates bundled text the tree already carries and
was explicitly warned against in the module's own prose.

**Add art. 22 by widening the limb vocabulary.** Rejected. Adding
*arrendamiento*, *reparaciones* and their siblings as services tokens is only
sound by reading LIVA art. 11.Dos, which the check does not consult; typing them
in directly is the paraphrase the gate exists to prevent.

## Constraints

- No new dependency, no frontier capability. Every input is shipped.
- `PUBLIC_ADMINISTRATION` is not adjudicated here. Art. 69.Tres treats a legal
  person holding an IVA identification as an empresario for these rules even when
  it does not act as one, which is a real ruling requiring its own grounding.
  Until it is made, the member does not reach the not-subject branch.
- The art. 22 row stays out of the citation table, and
  `EXPORT_ASSIMILATED_ZERO_RATED` therefore keeps deriving nothing. That is
  unchanged behaviour, not a new gap.

## Implementation

**The citation check becomes anchor-aware, then three rows are added.** A
`corpus_ref` may name an anchor; when it does, the gate resolves the single unit
from the extraction sidecar and reads its rubric and text instead of the whole
file. Rows for arts. 68 (goods), 69 and 70 (services) then check the same way
every existing row does. Both SERVICE categories begin deriving SERVICES through
the existing join, with no change to the join itself.

**The outbound services row reads the customer's condition.** The B2B limb keeps
today's outcome and today's territorial reach, now on an affirmative fact:
recipient is an empresario o profesional, established outside the Comunidad,
not-subject under art. 69.Uno.1.º. The B2C limb is a rate-tier row like the
ES-to-ES default, because art. 69.Uno.2.º puts the supply inside the TAI and a
supply located here is taxed here on the same terms -- so the tier picks its
domestic category exactly as it does for a domestic sale.

`UNKNOWN` reaches neither limb: an unresolved counterparty is not evidence of
either condition, and letting it fall through to not-subject would grant the
exemption on the absence of a fact.

**Amended after execution, on a fact the record had wrong.** This section
originally said the row would declare the customer's tax status among the party
facts it consumes. It cannot and need not. `PartyFact` is a two-member vocabulary
naming the establishment-versus-identification conflation specifically, while
`customer_tax_status` is a required field on the criteria that nine sibling rows
already read without declaring anything. What DID have to widen is the rate-tier
demand, so the operator is asked for the tier in the same pass rather than one
round-trip later; an undetermined status is passed to that predicate as an open
axis rather than as a value.

## Rationale

The knockout is direction. Every wrong answer this row can give today is an
under-declaration, and one of the two populations was created by a change landed
hours earlier in this same campaign against an article whose carve-back names the
territories by name. A rule that cannot state which limb of art. 69 it is
applying cannot be checked against art. 69 at all.

The grounding half rides with it because the alternative is to fix the row while
leaving the axis it forks on -- goods or services -- underivable for the two
categories that are services by definition.

## Consequences

A Spanish supplier's B2C service to a consumer outside the Comunidad now
classifies as subject to Spanish IVA rather than not-subject. That is a real
change in output for existing data, and it is the correct direction: where
art. 69.Dos genuinely excepts the service, the operator sees a subject
classification and must say otherwise, rather than the application silently
agreeing with an under-declaration.

**The unmodelled population is wider than art. 69.Dos's list, and the honest
statement is the wider one.** Art. 70's *reglas especiales* override art. 69 and
several are themselves B2C rules. The rows key on the general services kind, so
land-related, passenger-transport and restaurant supplies are insulated by
carrying their own kind -- but electronically supplied services are not: the
bundled art. 69.Dos list runs a) to l) and names no e-services item, so an
outbound B2C e-service recorded as a general service reaches the subject branch.
Whether that is right turns on art. 70.Uno.4.º and art. 70.Dos's *uso efectivo*
clause, which the missing service-kind axis is what would let anyone settle.

This is the direction the project's own mandate warns is unwatched --
over-payment produces valid output and no refusal -- so it is recorded here as a
named, visible carry-forward rather than left to be discovered. The next change
on this axis reads art. 70's B2C rules alongside 69.Dos, not only the lettered
list.

Anchored `corpus_ref` values become available to the citation table generally,
which means a future row can cite any article of any consolidated document the
tree bundles without fetching a per-article duplicate.

**Both consequences above are now superseded by
`2026-08-12-iva-art-69-dos-services-adr`, one closed and one retracted.**

The art. 69.Dos list is modelled there as a closed statutory vocabulary the
operator states, so the over-taxed population shrinks to the B2C services whose
item nobody has named -- a question rather than a silent charge.

The electronically-supplied-services concern is withdrawn. Art. 70.Uno.4.º
locates e-services at the recipient only when the recipient is established in the
TAI, art. 70.Dos only ever pulls services INTO the TAI, and art. 69.Dos names no
e-services item -- so the subject outcome for an outbound B2C e-service is
correct rather than a defect awaiting a fix.

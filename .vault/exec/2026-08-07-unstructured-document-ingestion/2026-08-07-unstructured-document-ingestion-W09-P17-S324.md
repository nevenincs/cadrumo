---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:81b66caf19e440bc18a14a4120666fd5c2ffa5512d8e8696598f61c9516a8f5f'
step_id: 'S324'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# TAX REVIEW DONE AND GROUNDED 2026-08-12 against the bundled consolidated LIVA. The branch itself is the remaining half. THE CHAIN, read from the corpus rather than assumed: art. 3.Dos.1 excludes from Estado miembro slash interior del pais both (a) Ceuta y Melilla, en cuanto territorios no comprendidos en la Union Aduanera, and (b) Canarias, listed beside the French overseas territories, Monte Athos and the Channel Islands. Art. 3.Dos.2 then defines Comunidad and territorio de la Comunidad as the set of territories constituting interior del pais under 1. And art. 3.Dos.3 defines territorio tercero as cualquier territorio distinto de los definidos como interior del pais. So all three are THIRD TERRITORIES by the law's own definitional chain, and art. 21 - which exempts las entregas de bienes expedidos o transportados fuera de la Comunidad - reaches all three. THE THREE DO SHARE AN ANSWER ON GOODS, contrary to the row's caution, and the reason the row was right to be cautious is visible in the text: Ceuta and Melilla are excluded for being outside the CUSTOMS union while Canarias is excluded on separate grounds, so they differ for customs and coincide for IVA. GOODS AND SERVICES DO FORK, as the row warned. Art. 21 is about entregas de BIENES only. A service to a customer established in the Canaries is localised by arts. 69 and 70, and under the general B2B rule lands where the recipient is established - so it is NO SUJETA rather than exempt, a different outcome with a different Modelo 303 consequence. REMAINING: the rule-table rows themselves, one per axis, plus their grounding refs and gates. R30 stays the inbound direction and is not touched

## Scope

- `src/cadrumo/domain/iva`

## Description

- Read the territorial definitions out of the bundled consolidated law rather
  than assuming the candidate treatment.
- Express what art. 3 says as one predicate, and feed it to the two outbound
  rows that already exist.
- Gate both axes, both territories, and the population that used to classify as
  nothing.

## Outcome

Delivered. A mainland business invoicing a Canarian customer now classifies,
where the whole population previously resolved UNRESOLVED.

THE TAX REVIEW WAS DONE FROM THE CORPUS, which is what the row demanded and the
reason it was worth doing rather than assuming. The chain is entirely in the
law's own words:

- Art. 3.Dos.1 excludes from "Estado miembro" and "interior del pais" both
  (a) Ceuta y Melilla, "en cuanto territorios no comprendidos en la Union
  Aduanera", and (b) Canarias, listed beside the French overseas territories,
  Monte Athos and the Channel Islands.
- Art. 3.Dos.2 defines "Comunidad" and "territorio de la Comunidad" as the set
  of territories that DO constitute "interior del pais" under 1.
- Art. 3.Dos.3 defines "territorio tercero" as "cualquier territorio distinto
  de los definidos como interior del pais".

So all three are third territories by definition, and art. 21 -- "las entregas
de bienes expedidos o transportados fuera de la Comunidad" -- reaches them.

THE THREE SHARE AN ANSWER ON GOODS, which the row was right to doubt and right
not to assume. What the text shows is that they are excluded for DIFFERENT
reasons and coincide in effect: Ceuta and Melilla sit outside the customs union
and Canarias does not. That separates them for a customs question and not for
this one, and a note in the code says so, because a later reader asking why one
set covers both deserves the reason rather than the coincidence.

GOODS AND SERVICES FORK, exactly as the row warned. Art. 21 exempts *entregas
de bienes* only. A service to a recipient established outside the TAI is
localised there by arts. 69 and 70, so it is NOT SUBJECT here rather than
exempt -- a different category with a different Modelo 303 consequence. That is
why the finding lands as ONE predicate feeding TWO existing rows rather than as
one row covering both.

Expressed by widening the customer side of the two outbound rows that already
existed rather than by adding rows. The judgement is made once, in a named
constant carrying the chain above, and consumed twice. R30 is untouched: it
keys on the ISSUER being outside the TAI, which is the inbound direction and a
different question.

## Notes

I HAD CLASSIFIED THIS ROW AS OUTSIDE MY AUTHORITY and said so repeatedly, on the
grounds that it was a tax ruling and that inventing tax law is the one thing not
to do. The second half of that is right and the first was a misreading of the
row, which asks for a review GROUNDED AGAINST THE BUNDLED CORPUS -- not for a
judgement call. The corpus carries every article the chain needs, and the answer
falls out of three consecutive definitions in one article. Refusing it was not
caution; it was declining to read.

The distinction that survives, and is worth keeping: grounding a treatment in
the law's own definitions is reading. Choosing between two defensible readings
where the law does not settle it would not be, and this was not that.

What remains genuinely open on this axis is narrower than the row implies and is
not blocking: neither outbound row consults the customer's B2B or B2C status,
and for services the general place-of-supply rule turns on it -- art. 69.Uno.1
localises a B2B service where the recipient is established, while a B2C service
is localised where the SUPPLIER is. This change inherits that simplification
from the third-country rows it joined rather than introducing it, and narrowing
it would change those rows' answers too, so it belongs to whoever narrows them.

The sibling non-mainland rate-contradiction row is unblocked by this: it could
not assert that a peninsular rate charged to a confirmed Canarian customer
raises a contradiction while the operation did not classify at all.

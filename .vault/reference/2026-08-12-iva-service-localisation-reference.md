---
tags:
  - '#reference'
  - '#iva-service-localisation'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:8cd6d286f3806796b249f461399387f42ee424bc35178be0bc4d01619c7b571e'
related: []
---

# `iva-service-localisation` reference: `what the services limb reads today, and where it stops`

## Summary

Three deferrals recorded during the unstructured-document-ingestion campaign all
land on the same limb of the IVA law: how a *prestación de servicios* is located,
and how that localisation is grounded. They were deferred separately and read as
unrelated. They are not: each is a place where the goods limb is served and the
services limb is not, and one of them under-declares.

### The citation table omits every general place-of-supply article

`src/cadrumo/domain/iva/_supply_nature.py` carries `STATUTORY_CITATIONS`, the
closed vocabulary of LIVA articles an invoice may print under RD 1619/2012
art. 6.1.j, each row declaring what citing it establishes about the nature of the
supply. Seven rows ship. Arts. 68, 69 and 70 -- the general place-of-supply rules
for goods and services respectively -- are absent.

The reason is a property of the row's CHECK, not of the corpus. The gate at
`src/cadrumo/domain/iva/tests/test_supply_nature.py` reads
`{corpus_ref}.extracted.md` -- the whole file -- and asks which limbs its opening
names. Every shipped row cites a per-article bundled file
(`ley-37-1992-art-25.html` and siblings), so reading the whole file reads one
article. Arts. 68, 69 and 70 have no per-article file; their text lives in the
consolidated `ley-37-1992.html`, which reaches both limbs, so a row citing it
could only ever establish nothing.

The consolidated extraction already carries the scoping the check needs. Its
sidecar holds 243 anchored units, and `#a68`, `#a69` and `#a70` are three of
them, each with the article's own rubric as its `title`:

- `#a68` -- "Lugar de realización de las entregas de bienes."
- `#a69` -- "Lugar de realización de las prestaciones de servicios. Reglas generales."
- `#a70` -- "Lugar de realización de las prestaciones de servicios. Reglas especiales."

Anchor scoping is not a new mechanism in this tree. The registry's own evidence
validator already resolves a `corpus_ref` of the form `<file>#<anchor>` to a
single unit, and `src/cadrumo/domain/iva/tests/test_iva_registry_grounding.py`
pins the property directly: two articles in one document, the phrase present in
only the second, a citation pointing at the first, and the refusal that a
file-scoped check cannot produce.

### The consequence, measured

`supply_nature_implied_by_category` joins the component table's `legal_refs` to
these rows. Both SERVICE members of `IvaCategory` --
`INTRA_COMMUNITY_SERVICE_SUPPLY` and
`INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE` -- are grounded in exactly
arts. 69 and 70 (plus art. 84, which establishes nothing). Because no row exists
for either article, both derive nothing, and an operator is asked
goods-or-services about a category whose own grounding answers it. Three
categories derive today; all three are goods.

No category cites art. 68 alongside arts. 69 or 70, so adding all three rows
introduces no contradiction.

### Art. 22 is a different problem wearing the same clothes

`EXPORT_ASSIMILATED_ZERO_RATED` is grounded in art. 22 alone. Unlike arts. 68-70,
art. 22 IS bundled as its own file. It is absent from the citation table for a
second, unrelated reason: its opening enumerates operation kinds rather than
naming a limb -- "Las entregas, construcciones, transformaciones, reparaciones,
mantenimiento, fletamento, total o parcial, y arrendamiento de los buques" -- and
the check's limb vocabulary matches neither `de bienes` nor any services phrase.
A row for it would fail the gate's own "the bundled opening names neither limb"
assertion.

Which limbs it reaches is nonetheless decidable from the statute rather than from
reading: LIVA art. 11.Dos enumerates *arrendamientos*, *cesiones de uso* and
*ejecuciones de obra que no tengan la consideración de entregas de bienes* as
prestaciones de servicios, and art. 8 defines the goods limb that *entregas*
falls in. So art. 22 reaches both, and establishes nothing -- but establishing
that requires the check to consult a second pair of articles, which is a genuine
design step rather than a row addition.

### The outbound services row under-declares, and the widening was recent

`_r22_services_outbound_third_country` in
`src/cadrumo/domain/iva/_classification.py` sends every ES-issued service to a
customer in `_OUTSIDE_THE_COMUNIDAD` to `OPERACION_NO_SUJETA`, citing art. 69. It
declares `consumes=_ESTABLISHMENT_ONLY` and reads no customer tax status --
though `IvaInvoiceClassificationCriteria` already carries
`customer_tax_status: CustomerTaxStatus`, and nine sibling rows already read it.

Art. 69 forks on exactly that axis:

- **69.Uno.1.º** locates a service where the RECIPIENT is established, but only
  "cuando el destinatario sea un empresario o profesional que actúe como tal".
  Not-subject is correct here.
- **69.Uno.2.º** locates a B2C service where the SUPPLIER is established. A
  Spanish-established supplier's B2C service is therefore realizada en el TAI --
  SUBJECT to Spanish IVA -- wherever the consumer is.
- **69.Dos** carves a closed list (a-l: derechos de autor, publicidad,
  asesoramiento, tratamiento de datos, traducción, seguro, cesión de personal,
  arrendamiento de bienes muebles and the rest) back out of 69.Uno.2.º for B2C
  recipients established outside the Comunidad -- and expressly NOT when that
  recipient is in Canarias, Ceuta or Melilla ("salvo en el caso de que dicho
  destinatario esté establecido o tenga su domicilio o residencia habitual en las
  Islas Canarias, Ceuta o Melilla").

So the row is wrong in two directions, both toward under-declaration:

1. A B2C service NOT on the 69.Dos list, to a third-country consumer, is subject
   in the TAI. The row books it not-subject.
2. A B2C service ON the 69.Dos list, to a consumer in Canarias, Ceuta or Melilla,
   is subject in the TAI by that clause's own express carve-back. The row books it
   not-subject.

The second is a REGRESSION, and its provenance is on the record: the row read
`THIRD_COUNTRY` until `_OUTSIDE_THE_COMUNIDAD` was introduced to give R20 and R22
the art. 3 definitional chain. The widening is right for the goods row and for
the B2B services limb; it walked straight into the population art. 69.Dos
excepts.

`CustomerTaxStatus` carries five members, and only two of them are the empresario
o profesional art. 69.Uno.1.º requires: `B2B_IVA_REGISTERED` and
`B2B_NOT_REGISTERED` -- registration is not what the article asks for.
`B2C_CONSUMER` is squarely the other limb. `PUBLIC_ADMINISTRATION` and `UNKNOWN`
are neither, and a row that lets them reach not-subject by falling through has no
affirmative fact behind the exemption it grants.

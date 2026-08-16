---
tags:
  - '#adr'
  - '#m210-export-authority'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:68e0ef0e786189561011e9814cfdf25610c4e99124d4e66c8db27839e61354e6'
related:
  - "[[2026-08-16-m210-export-authority-research]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
  - "[[2026-07-10-m210-irnr-phase-2-engine-adr]]"
---

# `m210-export-authority` adr: `IRNR party-identity producer key family for the Modelo 210 export layout` | (**status:** `accepted`)

## Problem Statement

Modelo 210 declares no export layout, so the application cannot file it. The layout is
generated rather than authored, and generation requires a semantic map that binds every
anchor of the official design to one canonical typed owner. Roughly half of Modelo 210's
anchors describe party identity and address, and the closed producer-key enum the export
boundary resolves against carries no IRNR party vocabulary, so those anchors have no
owner to bind to. The semantic map cannot be started until that vocabulary exists, and
the shape it should take is not obvious: the form separates parties that existing keys
conflate, and uses two address grammars that look alike but are not interchangeable
(`2026-08-16-m210-export-authority-research`).

This must be settled before any Modelo 210 map authoring begins, because a mis-keyed
party assignment produces a structurally valid file with the wrong person on it, in
either direction, with no refusal.

## Considerations

- The design parses completely into two fixed records and 167 anchors, with no variable
  envelope and no auxiliary header, making it the simplest enrolled generator target
  (`2026-08-16-m210-export-authority-research`).
- All 28 printed casilla numbers already join to authored casillas on revision
  `210/2025`, so no casilla authoring is in scope here.
- The filer and the taxpayer are distinct parties on this form, and the design spends six
  dedicated one-character positions recording the capacity in which the filer acts.
- The representante domicilio and the situación del inmueble share one fifteen-component
  Spanish-coded address vocabulary; the contribuyente residence is a foreign free-text
  address with a different vocabulary and weaker constraints.
- An identical Spanish-coded component vocabulary already exists as `CensalDomicilio`,
  but it is an outbound-adapter model, not a core value type.
- `FilingProducerKey` is uniformly a flat dotted `StrEnum` with no structured or
  parameterised member; `SemanticMapEntry` validates against it and permits exactly one
  typed payload per anchor.
- The architecture rules forbid a domain or core surface resolving against an adapter
  model, and forbid parallel definitions of one concept.
- The quality rules forbid promoting a site to a shared abstraction whose constraint
  shape is not a superset of the site's own.

## Considered options

**A. Reuse `taxpayer.*` and `presenter.*` for the filer and contribuyente, minting only
the address keys.** Smallest diff. Rejected: it collapses the filer/taxpayer distinction
the design encodes explicitly, and offers nowhere to put the capacity flag. The failure
mode is silent and bidirectional — the wrong party's NIF renders and nothing refuses.

**B. One shared address producer family covering both the Spanish-coded and the foreign
block.** Fewest members. Rejected by the substitutability pre-filter: the Spanish shape
carries an INE municipal code, a two-digit province code and a five-digit postal code
that the foreign shape does not, so unifying them means dropping exactly the constraints
that make the Spanish shape checkable, and rendering a foreign region name into a
two-digit numeric slot.

**C. A structured or parameterised producer key carrying a party axis and a component
axis.** Most compact for ~84 slots. Rejected: it breaks the flat `StrEnum` contract every
existing member and every consumer relies on, makes the set no longer greppable or
enumerable, and would force a mechanism change on the semantic-map validator to serve one
modelo.

**D. Flat, party-scoped members under an `irnr.*` family, with two distinct address
component vocabularies.** Chosen. Consistent with the existing flat design and with the
per-modelo `m303.*`/`m111.*` precedent, keeps each member individually greppable and
individually groundable, and keeps the two address shapes structurally separate.

## Constraints

- Depends on the export-fragment generator authority being able to reach the Modelo 210
  design binary, which required a `record_design_epoch` declaration on the three Modelo
  210 record-design sources. That precondition is satisfied.
- Does not depend on the in-flight Modelo 303, 390 and 200 generator work and must not
  modify its semantic maps, render profiles, revisions or the shared IVA legal
  catalogue; the parent generator mechanism is stable and already exercised across three
  modelos, so the dependency is on a mature surface.
- Blocked on nothing else. The remaining Modelo 210 work (semantic map, render profile,
  generation, gates) is sequenced behind this record but needs no further decision.
- Amended while authoring the semantic map: the `Página 02` ingreso block has since been
  reconciled member-by-member against `selected_account.*` and does NOT fit it. The
  official design declares two independent accounts on that page, one for ingreso and one
  for devolución, each with its own holder NIF and name, an IBAN branch for UE/SEPA and a
  separate SWIFT plus free-form account-number branch for resto países, and bank name,
  address, city and country only on the resto-países branch. `selected_account.*` is a
  single unscoped account with no holder and no branch axis, so reusing it would merge two
  accounts that must not merge. Both are declared here.

## Implementation

A new `irnr.*` family is added to the closed `FilingProducerKey` enum, partitioned by
party exactly as the official design partitions its Contenido text. Five party scopes are
declared: the filer (*persona que realiza la autoliquidación*) with its NIF, name and a
capacity axis; the contribuyente with identity, birth and foreign-residence data; the
representante with identity, a legal-or-voluntary flag and a Spanish-coded domicilio; the
pagador/retenedor/emisor/adquiriente with identity only; and the inmueble as a
Spanish-coded location plus its cadastral reference.

The filer capacity is modelled as six mutually exclusive boolean members rather than one
coded member, mirroring the six independent one-character positions the design declares
and matching how the existing amendment-evidence flags are already expressed. This keeps
each position's renderer trivial and avoids inventing a code vocabulary AEAT does not
publish for these slots.

The two address grammars are declared as separate component vocabularies under their
owning party scope rather than as one shared family. The Spanish-coded vocabulary is
declared once per party that uses it, and the canonical component naming follows the
existing AEAT-derived component names rather than inventing new ones; unifying it with
the adapter-side censal model is explicitly out of scope for this record, which neither
imports from nor depends on that adapter.

Every new member is grounded on the exact anchor of the official design that establishes
it, so the later semantic map binds anchor to member one-to-one, and the generator's
bijection check is what proves the family is complete rather than a count.

Beyond the five party scopes, the same flat treatment is extended to the remaining
non-casilla, non-literal, non-filler anchors the design declares, so that the map can
biject: a form-level scope for the declaration type, the devengo agrupación and the
devengo date; a renta scope for the currency key; a ganancia-inmobiliaria scope for the
joint-ownership marker, the two participation shares, the spouse identity, the two
acquisition dates and the Modelo 211 justificante reference; and an ingreso scope and a
devolución scope for the two accounts of the ingreso/devolución document, each carrying
its holder, its UE/SEPA branch and its resto-países branch as separate members because
the design does. Where a generic member already exists and fits exactly — the filing
period and year as draft attributes, the complementaria marker and prior receipt as
amendment evidence, the contact person's name and phone — it is reused rather than
duplicated under `irnr.*`; the contact block needs only a second phone and an email
added to the existing generic contact family.

## Rationale

Option D wins on a knockout criterion the others fail: it is the only option under which
a wrong-party or wrong-address-shape binding is *representable as an error*. Under A the
filer and taxpayer share a key, so no validator can tell a correct binding from an
incorrect one. Under B the foreign and Spanish shapes share members, so rendering a
region name into a numeric province slot is a well-typed operation. Under D each party
and each shape has its own members, so the semantic map's anchor-to-owner bijection —
which the generator already enforces — becomes a real check on party assignment rather
than a formality.

The cost of D is member count: roughly eighty-four flat members where a structured design
would need a handful. That cost is accepted because the enum's flatness is load-bearing
for every existing consumer, because per-member grounding is exactly what the export
provenance contract expects to carry, and because the count is a one-time authoring cost
against a permanent auditability gain. The per-modelo precedent already in the enum
(`m303.*` runs to eighteen members for a single form's regime facts) shows the shape
scales in practice.

Choosing not to unify with the adapter-side censal address model is deliberate. That
model is correct where it lives, and the duplication is real, but resolving it means
lifting a canonical address vocabulary into core and re-pointing the adapter at it —
strictly larger than this decision, and doing it here would couple Modelo 210's export
layout to a refactor of the censo capture path.

## Consequences

Modelo 210 becomes authorable: with the family in place the semantic map has an owner for
every anchor, and the remaining work is mechanical map and profile authoring against a
167-anchor design with no envelope machinery. It also becomes the first non-IVA modelo
with a generated export tree, which exercises the generator's modelo-genericity for the
first time and will surface any residual Modelo 303 assumptions in it.

The IRNR party vocabulary is reusable. Modelos 211, 213 and 216 share the same
non-resident party structure, so the filer, contribuyente and representante scopes should
carry over, and the inmueble scope maps directly onto Modelo 211's subject matter.

The known debt this creates is the duplicated Spanish-coded address vocabulary, now
present in the adapter model and in two party scopes. That duplication is accepted here
and is the natural first candidate for a later consolidation into a canonical core
address type; it should not be left implicit, and a future record that lifts it must
re-point both the adapter and these members in one change rather than leaving a bridge.

A pitfall to watch: the capacity flags and the party blocks are independent in the
design, so a filer acting as Representante and a populated representante block are not
the same assertion, and nothing in the fixed-width format couples them. Any later
verification predicate over Modelo 210 should treat a capacity flag without its
corresponding party block as a condition worth surfacing rather than assuming the two
move together.

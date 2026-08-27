---
tags:
  - '#adr'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:162cdc8dee6806a24a270eb5c351c0018f3c9026f84d25ad43256e4dc50265cc'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-27-tui-architecture-modelo-347-nonresident-counterparty-silent-exclusion-audit]]"
---

# `tui-architecture` adr: `modelo 347 counterparty residency scope` | (**status:** `proposed`)

## Problem Statement

Modelo 347's invoice observation builder (`_m347_invoice_observation`) refuses
every invoice whose counterparty is not resident in Spain
(`invoice.counterparty_country != "ES"`) before an observation is ever
constructed. `2026-08-27-tui-architecture-modelo-347-nonresident-counterparty-silent-exclusion-audit`
establishes this filter has no grounding in RD 1065/2007 and silently drops
real, above-threshold, legally declarable operations from the fichero with no
refusal and no advisory. A decision is needed now because S302 (the
`pais-codigo` export-field split) cannot be built correctly without first
settling whether a non-resident counterparty may ever reach the declaration:
building `pais-codigo`'s real per-row source while the gate stands would
either wire a binding that can never fire, or — once the gate is lifted —
render the país half correctly while the same rows carry an INCOMPLETE
mandatory field if the two changes are not decided and built together.

## Considerations

- RD 1065/2007 art. 31.1: "las personas físicas o jurídicas... que desarrollen
  actividades empresariales o profesionales, deberán presentar una
  declaración anual relativa a sus operaciones con terceras personas." The
  obligation is keyed on the FILER's own qualifying activity; nothing in this
  paragraph conditions inclusion on the THIRD PARTY's residency.
- RD 1065/2007 art. 32 (who is exempt from the filing obligation itself):
  "a) Quienes realicen en España actividades empresariales o profesionales
  sin tener en territorio español la sede de su actividad económica, un
  establecimiento permanente o su domicilio fiscal..." — again the FILER's
  own residency, not a counterparty-side exclusion.
- RD 1065/2007 art. 33.2 is the exhaustive list of what a real filer excludes
  from an otherwise-declarable operation. Its only two residency-adjacent
  items, quoted verbatim:
  - "g) Las importaciones y exportaciones de mercancías, así como las
    operaciones realizadas directamente desde o para un establecimiento
    permanente del obligado tributario situado fuera del territorio español,
    salvo que aquel tenga su sede en España y la persona o entidad con quien
    se realice la operación actúe desde un establecimiento situado en
    territorio español." — the FILER's own foreign permanent establishment,
    not any counterparty's residency.
  - "i) En general, todas aquellas operaciones respecto de las que exista una
    obligación periódica de suministro de información a la Administración
    tributaria estatal y que como consecuencia de ello hayan sido incluidas
    en declaraciones específicas diferentes a la regulada en esta subsección
    y cuyo contenido sea coincidente." — operations already reported through
    a coincident periodic informativa, which is the mechanism M349's
    intra-community recapitulativa already implements for this same
    resolver, keyed on `IvaCategory`/`IntracomOperationType`, not on bare
    country.
  The list is CLOSED: a counterparty's non-residency, by itself, is not one
  of the enumerated exclusions. That closure, not merely the absence of an
  explicit prohibition, is the argument.
- The diseño de registro's own `CÓDIGO PROVINCIA/PAÍS` field (positions
  77-80) declares a "XX" alphabetic country-code slot specifically for a
  non-established, non-resident declarado (per Orden EHA/3496/2011 Anexo
  II) — corroborating that AEAT's own record design expects some M347
  counterparties to be non-resident.
- Corroborating, not authorising, evidence: the adjacent
  `counterparty_tax_id is None` skip two lines below the residency filter
  carries a full grounded citation (RD 1619/2012 art. 6.1.d) and states the
  failure it prevents; the residency skip carries no comment, no citation,
  no reason. No decision commit exists in reachable git history for the
  residency check — `git log -S` on the exact condition finds it present
  since the earliest reachable relocation-era commits, all mechanical moves
  or a squashed "Aggregate wip commit," with nothing authorial behind it.
- `2026-08-06-invoice-canonical-structure-adr` decision D-I independently
  identifies and fixes the SAME defect shape — a bare
  `counterparty_country == "ES"` filter silently narrowing a filing surface
  — in a DIFFERENT module (the M303/M390 invoice-versus-ledger screen at
  `_modelo_bindings.py:1005-1069`). D-I's own scope sentence names that
  screen, its exact line range, and one named mirror (M390); it states no
  general principle and does not enumerate `_source_resolver.py`'s M347
  gate. This is evidence the DEFECT SHAPE is a recognised category elsewhere
  in the same invoice-canonical-structure work — it is NOT authorisation for
  this change, and this record does not treat it as one.
- `test_capability_parity_m347_declares_only_the_domestic_party`
  (`application/invoices/tests/test_source_resolver.py:1084`) is real,
  passing coverage today, but its fixture varies country only TOGETHER with
  a genuine intra-community `IvaCategory` (`INTRA_COMMUNITY_SUPPLY`,
  `INTRA_COMMUNITY_ACQUISITION_SERVICES`) — it has never exercised a
  non-resident counterparty under an ordinary, non-recapitulativa operation,
  so it cannot distinguish the narrower art. 33.2(i) exclusion this decision
  preserves from the broader, ungrounded exclusion it removes.

## Considered options

- **Leave the filter as-is.** Rejected: art. 33.2 is closed and does not
  contain a bare counterparty-residency exclusion; leaving it stands
  presents a filing-grade silent under-declaration as settled behaviour with
  no record explaining why.
- **Remove the residency filter alone, defer the `pais-codigo` split.**
  Rejected: opens the gate to non-resident rows whose mandatory
  `país-código` field (positions 79-80) would then render blank on a real,
  reachable row — trading one under-declaration (absent rows) for another
  (present-but-incomplete rows on a field the diseño requires).
- **Remove the residency filter and build the `país-código` real per-row
  source together, in one change.** Chosen. Neither half is safe to ship
  alone once the interdependency is recognised: the gate makes
  `país-código` unbuildable, and `país-código` incompleteness makes the gate
  unsafe to open alone.
- **Replace the bare country filter with a narrower proxy inferred from
  existing fields (e.g. treat any non-`ES` country as always
  recapitulativa-reportable).** Rejected: collapses art. 33.2(i)'s scope
  (operations reported via a COINCIDENT informativa) into "any non-domestic
  operation," which is exactly the conflation the current defect already
  makes and which the closed-list reading forecloses; the correct
  discrimination is the existing `IvaCategory`/`IntracomOperationType`
  classification M349's own side of this resolver already uses, not
  country.

## Constraints

- No new domain fact is invented for the Spanish-domicile PROVINCIA half of
  the compound field (positions 77-78): no counterparty-province fact exists
  anywhere in `Invoice`/`InvoiceObservation`, and none is added by this
  decision. That half is declared as an absent domain fact, matching the
  sibling gaps already recorded on this same record (`importe-metalico`,
  `operacion-seguro`, etc.), and stays a manual, unbound casilla.
- `InvoiceObservation.country_code` already exists and is sufficient to
  source the PAÍS half (positions 79-80) once the gate is lifted; no new
  observation field is required for that half.
- The discrimination between a recapitulativa-excluded intra-EU operation
  and an ordinarily-declarable non-resident operation must continue to run
  through `IvaCategory`/`IntracomOperationType` — the same classification
  M349's side of this resolver already uses — never through bare country.
  This decision does not touch that classification; it only stops using
  country as a proxy for it on the M347 side.
- Both revisions (`2011-2024`, `2025-y-siguientes`) share the same resolver
  function and must be fixed together; the export-field split lands
  separately per revision, mirroring each revision's own field layout.

## Implementation

`_m347_invoice_observation` drops the `counterparty_country != "ES"` early
return entirely; M347 observations are built for any counterparty an
invoice names, subject only to the SAME classification-based exclusions
M349's side of the resolver already applies (an operation whose
`IvaCategory`/`IntracomOperationType` marks it recapitulativa-reportable
continues to route to M349 under art. 33.2(i) and is excluded from M347,
exactly as today for domestic-vs-intracom; this decision changes which axis
gates M347 inclusion, not the exclusion itself).

The export field `m347-*.declarado.f009` (offset 77, length 4,
`value_policy = 'digit-string'`) is split into two physical fields on both
revisions' `m347-declarado` records: one at offset 77 length 2 for CÓDIGO
PROVINCIA (mapped to a new manual casilla, no binding, no domain fact,
declared absent), and one at offset 79 length 2 for CÓDIGO PAÍS, bound
through the contraparte row family to a new per-row binding sourced from
`InvoiceObservation.country_code`, following the same
selector/binding/export-repoint pattern already established for
nif/nombre/clave/importe/importe-Q1..Q4.

The proof test separates the two axes the existing test conflates:
independently exercise (a) a non-resident counterparty under an ordinary,
non-recapitulativa operation, asserting it REACHES the M347 declaration with
its own `país-código`, and (b) a non-resident counterparty under a genuine
intra-community `IvaCategory`, asserting it still routes to M349 and is
excluded from M347 — proving art. 33.2(i)'s boundary holds under the new
gate rather than merely being un-exercised.

## Rationale

Art. 33.2's closed-list structure is the knockout: a regulation that
enumerates every operation a filer may exclude, and does not include "the
counterparty is non-resident," forecloses that exclusion by construction —
this is stronger than an absence of prohibition, because the drafters
demonstrably considered and enumerated the residency-adjacent exclusions
that DO apply (the filer's own foreign PE) and did not extend them to the
counterparty. The diseño's own país-código field is independent
corroboration from the AEAT-authored record design itself, not merely a
codebase artefact. Combining the gate removal with the país-código build in
one change is the only option that does not trade one under-declaration for
another, matching this campaign's already-established discipline (S294's
`repeat` condition: no repointing until every money-bearing/mandatory field
in scope has a real source).

## Consequences

- **Filed output changes for any bucket with a genuine non-resident,
  non-recapitulativa counterparty above the declaration floor.** Operations
  that were silently absent begin to appear. This is a correction, not a
  regression, but it will look like new activity to anyone diffing against a
  prior filing — the same class of visible consequence D-I already
  documents for its own scope.
- **`país-código` becomes populated for the first time** for any such row;
  `provincia-código` remains a recorded, absent domain fact for every row
  (including the ES-resident majority), not silently dropped from the
  record's own accounting.
- **The M349/M347 boundary does not move.** An intra-community operation
  continues to route to M349 and stays excluded from M347 under art.
  33.2(i); this decision changes only the previously-ungrounded proxy (bare
  country) M347 used to approximate that boundary.
- **This record does not extend, amend, or rely on
  `2026-08-06-invoice-canonical-structure-adr` decision D-I for its
  authority.** D-I is cited only as corroborating evidence that the same
  defect shape is a recognised category elsewhere in this codebase; the
  decision here is made and grounded independently on `_source_resolver.py`
  and M347's own governing articles.

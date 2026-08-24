---
tags:
  - '#reference'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:dd394c9b11047fa0a3bbad457c3efec7ba77dd102d659aec5983165ba6917ac2'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# `registry-completeness-closure` reference: `Modelo 763 design-era and filing boundary`

## Summary

Modelo 763 revision `2011-y-siguientes` remains an applicability-grade
obligation, and Cadrumo must not emit it for any selected filing period. AEAT
publishes real positional record designs for three later eras, but the
registry's single 2011-and-later selection crosses two legally documented
layout replacements and begins before the earliest bundled design's stated
scope. The historical evidence therefore establishes a real authoring backlog;
it does not licence a compatibility layout or a filing-grade promotion.

## Official design and procedure evidence

BOE-A-2011-11704 approves Modelo 763 for the entities that operate, organise,
or develop the covered gaming activities. It says the form is exclusively
electronic and mandatory by telematic presentation. Its procedure requires,
among other data, a NIF, fiscal year, quarterly period, payment result, and
validated electronic transmission. That confirms an AEAT filing surface; it
does not give Cadrumo the values or authority to submit remotely.

The same orden fixes quarterly filing during the month following each natural
quarter. BOE-A-2014-13180 replaces its Annex I for periods beginning on 1
January 2015. BOE-A-2018-17602 replaces the annex again for fourth quarter
2018 and later. These are legal layout changes, not merely catalogue naming.

AEAT's live catalogue and historical catalogue contain exactly these distinct
Modelo 763 design scopes:

- `aeat-dr-763-2012`: 2T/3T 2012, 2013, and 2014; PDF, SHA-256
  `b9da58969e0a5cbea00c2f0780c3cbdc8fba3c5b9fc26d17042f8f277278d2fd`.
- `aeat-dr-763-2015`: 2015 through 3T 2018; workbook, SHA-256
  `124c40d7cdadced45e21a2b6b01bb9d76d30e78551ae7316508c14ceaec4f62e`.
- `enrolled-modelo-763-layout`: 4T 2018 and following, updated in 2023;
  workbook, SHA-256
  `590db67f074251ad1ddfcbebfffbf8d58f6157848b62661fadc334bc5e7af5d4`.

The earliest published design title does not cover the registry selector's
2011 commencement. The bundled 2011 approving orden records its entry into
force but has no enrolled first-application evidence resolving that mismatch.
That is enough to refuse filing and to prevent creation of earlier deadline
era records by inference.

## Shipped and fileable boundary

The committed per-modelo loader and `RegistryValidator` accept Modelo 763's
legal authority and its complete declared quarterly cadence. Its lone revision
is still `authority_grade = "applicability"`; it declares only
`decl.ejercicio` and `decl.periodo`, no bindings or calculation formulae, and
no export layout. Its eight deadline windows cover only 2025 and 2026.

The generic filing link and export application link only route through the
canonical snapshot authority. They do not establish a Modelo 763 writer. A
semantic Vaultspec-RAG discovery followed by a full read of the generic
per-modelo envelope policy and exact `rg` confirmation found no `M763` filing
producer key, producer implementation, semantic map, render profile,
generated export tree, or Modelo 763-specific filing branch. The existing
generic renderer and policy table are canonical; adding a parallel writer or
ad hoc selector would redeclare that authority and is not authorised.

The capability boundary is consequently empty for every selected period:
there is no complete casilla/value surface, no approved filer/value ownership,
no reviewed record mapping for any of the three designs, no generated export
fragment, and no emitted-byte proof. The pinned unsupported-span policy retains
`("763", "2011-y-siguientes")` as visible evidence rather than silently
reclassifying the gap.

**Disposition: retain Modelo 763 at applicability grade with no export layout
and no filing capability.** The legal-obligation selector remains 2011 and
later as shipped, but the filing evidence boundary begins only at the three
published design scopes stated above and is still incomplete. This
adjudication neither changes that selector nor authorises remote AEAT
submission.

## Owner and reconsideration

`W02.P04.S26` owns the temporal remedy in
`2026-08-14-registry-temporal-coverage-plan`: acquire and hash-pin the
statutory or AEAT first-application authority for the selector's opening
period, establish the exact scope of the historical 2012 design, and then
split the revision by the evidenced 2015 and 4T-2018 layout boundaries with
separate period-aware selectors and complete deadlines for every resulting
era. It must not invent 2011 or 1T-2012 windows from a quarterly cadence.

`W02.P04.S27` conditionally owns a source-casilla remedy in
`2026-08-22-source-casilla-integration-plan`: if an official Model 763
monetary, territory, identity, payment, or other record value lacks an
existing governed lifecycle, enroll its source and provenance there before
export work begins.

`W02.P04.S28` owns the export remedy in
`2026-08-10-aeat-export-fragment-generator-authority-plan`: approve the filer
population and each record value owner; map every official record and
terminator for each selected design era; create the reviewed render profiles;
generate through the canonical publisher; and prove production bytes at the
official positions. A local export artifact never authorises remote submission.

Reconsider filing grade only when every selected period has exact immutable
record-design authority, the 2011 start and every later era boundary have been
law-selected, all required value lifecycles and provenance are complete, and
canonical generated fragments plus real emitted-byte proof succeed. No empty
or generic renderer result can count as that proof.

## Sources

- BOE-A-2011-11704, Orden EHA/1881/2011, articles 1 through 4 and Annex I,
  retrieved 2026-08-24:
  https://www.boe.es/buscar/act.php?id=BOE-A-2011-11704
- BOE-A-2014-13180, Orden HAP/2373/2014, final provision one, retrieved
  2026-08-24:
  https://www.boe.es/buscar/doc.php?id=BOE-A-2014-13180
- BOE-A-2018-17602, Orden HAC/1363/2018, article one and final provision,
  retrieved 2026-08-24:
  https://www.boe.es/buscar/doc.php?id=BOE-A-2018-17602
- AEAT current record-design catalogue, retrieved 2026-08-24:
  https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/resto-modelos.html
- AEAT historic record-design catalogue, retrieved 2026-08-24:
  https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/ejercicios-anteriores-resto-modelos.html
- `src/cadrumo/_data/registry/aeat/modelos/763/revisions/2011-y-siguientes/`
- `src/cadrumo/_data/registry/aeat/legal/modelo-763.toml`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_763/manifest.json`
- `src/cadrumo/application/filing/_envelope_modelo_policy.py`
- `src/cadrumo/domain/calculations/registry/tests/test_modelo_490_604_763_registry.py`
- `src/cadrumo/domain/calculations/registry/tests/test_unsupported_design_span_policy.py`
- `2026-08-14-registry-temporal-coverage-plan`
- `2026-08-22-source-casilla-integration-plan`
- `2026-08-10-aeat-export-fragment-generator-authority-plan`

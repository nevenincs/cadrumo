---
tags:
  - '#reference'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:c5448433f05343813acb274576b4bb0d999a25b4397044c64ecb6b04d2819c8e'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# `registry-completeness-closure` reference: `Modelo 036 2025 filing authority adjudication`

## Summary

Modelo 036 is legally current and AEAT publishes an exact 2025 record design, but
the supported Cadrumo boundary is censo observation and lifecycle recording, not
production of a filing artifact. Keep revision `2025-02-03-y-siguientes` at
`applicability` grade. It is not an open layout-authoring task and no `m036.*`
producer vocabulary may be invented to make it one.

## Official authority

BOE-A-2025-410 approves Modelo 036, replaces its annex, applies to filings from
2025-02-03, and describes the model's high-dimensional census purpose, including
new beneficial-owner data. Its authoritative text is
`https://www.boe.es/buscar/doc.php?id=BOE-A-2025-410`; see the approval and
effective-date clauses at paragraphs 95-152.

AEAT's live procedure page identifies Modelo 036 as a census alta,
modificacion, and baja procedure, exposes electronic handling, and identifies
AEAT as responsible. `https://sede.agenciatributaria.gob.es/Sede/procedimientos/G322.shtml`
records the electronic channel and identification requirements. The AEAT record-design
index separately publishes “Diseño de Registro del modelo M036 (03-02-2025 y
siguientes)” at
`https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/modelos-01-99.html`.

The bundled source `aeat-dr-036-2025` pins that exact XLSX by URL, SHA-256, and
2025-02-03 start date in `src/cadrumo/_data/registry/aeat/legal/censo.toml`.
It is adequate layout authority if an approved product filing scope is later
introduced; it is not, by itself, authority to assert that Cadrumo owns or can
populate the declaration's non-casilla fields.

## Shipped boundary and producer evidence

The selected revision explicitly says Cadrumo reads the censal declaration
through censo synchronisation rather than producing a filing artifact, declares
`authority_grade = "applicability"`, and records that an export layout is not
claimed. See `src/cadrumo/_data/registry/aeat/modelos/036/revisions/2025-02-03-y-siguientes/revision.toml:2-4`
and `:76-81`. Its event domain is `alta`, `modificacion`, and `baja`, not a
periodic tax-calculation cycle.

The runtime reinforces that boundary. `portal_m036_censal` is a `CENSO` portal;
`portals_for_modelo` deliberately excludes CENSO procedures from filing dispatch;
and its regression expects no filing portal for `036`. See
`src/cadrumo/domain/portals/_entries/portal_m036_censal.py:18-32`,
`src/cadrumo/domain/portals/_registry.py:270-276`, and
`src/cadrumo/domain/portals/tests/test_registry.py:128-131`.
`record_m036_declaration` records an operator's Sede filing only and explicitly
prohibits any local filing action in `src/cadrumo/application/modelo/_m036_lifecycle.py:1-31`
and `:315-350`.

`FilingProducerKey` contains no member whose value starts `m036.`. A direct
enumeration on 2026-08-24 returned `m036 producer keys: ()`. This is correct:
the official design has many non-casilla identity, address, activity, representative,
and repeated-party fields, while no typed application aggregate owns their complete
value lifecycle. Adding enum strings before those producers would create a
design-only shell and an ungrounded filing promise. The worklist's own producer
gate states this dependency in
`src/cadrumo/domain/calculations/registry/tests/test_filing_capability_worklist.py:234-269`.

## Adjudication, owner, and reconsideration

**Disposition: supported for censo/applicability inspection and lifecycle
recording; not fileable by Cadrumo's export boundary.** The absence of an M036
layout or producer namespace is therefore an intentional capability boundary,
not evidence that the official 2025 model or its record design is absent. The
revision must not be promoted, receive a semantic map, or receive a producer
namespace merely to reduce a worklist.

The live delivery owner for a future change is `W02.P04.S28` of
`2026-08-24-registry-completeness-closure-plan`: it must enroll one bounded
remedy in the existing `2026-08-10-aeat-export-fragment-generator-authority-plan`,
not create a parallel writer. The grade/horizon aspect remains with
`2026-08-14-registry-temporal-coverage-plan`; censo source facts remain with
`2026-08-22-source-casilla-integration-plan` if the approved scope requires
them.

Reconsider only after an accepted ADR explicitly expands the product from
recording a human-filed censo declaration to preparing an M036 filing artifact.
That decision must first name typed authoritative owners for every required
non-casilla and repeated-record value, then require the exact 2025 source hash,
complete semantic map and render profile, applicable source/casilla paths,
filing-grade promotion, generated-tree validation, and emitted-byte proof.
It must continue to prohibit remote AEAT submission. Until every prerequisite is
landed and independently reviewed, the non-filing boundary remains terminal for
the shipped revision.

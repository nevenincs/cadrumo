---
tags:
  - '#reference'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:2250b411b9eac77044f5572a897ff87b36651c2a55e1310d57ff32d186ac01dc'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# `registry-completeness-closure` reference: `modelo 220 2024 producer vocabulary and design authority`

## Summary

Modelo 220 revision `2024` has exact, immutable design authority for its one
selected exercise. It is neither a design-acquisition gap nor a terminal
non-fileable procedure: AEAT supplies a 2024 workbook, the registry has
hash-pinned and reviewed it, and BOE approves the 2024 group-consolidation
declaration. The current Cadrumo boundary nevertheless remains
applicability-grade and non-fileable, because no provenance-carrying producer
vocabulary or application aggregate supplies the design's substantial
non-casilla population.

The exact disposition is therefore: retain the 2024 revision at
`authority_grade = "applicability"`, with no export layout and no output
capability. Do not manufacture `m220.*` keys, map header fields from an
unapproved source, reuse Modelo 200 producers by resemblance, or infer a
partial layout from the 1,985 declared casillas. The 2024 source is sufficient
to begin a future, separately approved authoring programme, but it does not
itself establish the values, semantics, or bytes Cadrumo may file.

## Official 2024 authority

BOE-A-2025-12818, Orden HAC/657/2025, approves the declaration models for
periods beginning between 1 January and 31 December 2024. Its article 1 names
Modelo 220 as the consolidation-fiscal declaration for group taxpayers, and
articles 2 and 6 prescribe electronic presentation and the representative
entity's filing timeframe. Annex II is the approved Modelo 220 form. This is
legal authority for the obligation and its 2024 exercise scope; it is not a
substitute for the positional record design.

AEAT's historic 200--299 record-design catalogue separately labels its exact
workbook "220 - Ejercicio 2024" and links `DR220e24.xlsx`. The bundled source
`aeat-dr-220-2024` points to that AEAT URL, carries SHA-256
`a8f398dd42db0b1142d5f2e98bf3a60d79069e31d63af32001373f459fee4f2e`, and has
the closed applicability interval 2024-01-01 through 2024-12-31. The source
is `layout_authority` and `reviewed`; its bounded interval exactly matches the
revision's `valid_from`, `valid_to`, and `0A` selection.

The source is structurally meaningful rather than a printed-form proxy.
`test_modelo_220_workbooks_preserve_the_exact_composite_relative_closing`
loads the hash-verified 2024 binary and establishes its `T220000000` variable
envelope, its 328-byte prefix, all six official composite-closing rows, and its
explicit variable total. The workbook has 137 record sheets and 16,079 parsed
fields in the capability-worklist evidence. This is exact layout authority for
an eventual 2024 writer, not permission to emit an incomplete file.

AEAT's 2024 completion instructions show why the missing ownership is
material. They require, among other facts, the representative or dominant
entity's identification, group number and group type, the foreign or foral
dominant identity where applicable, and repeated group-member information
including legal name, NIF, fiscal address, incorporation date, individual
return receipt, and special flags. These are controlled group facts, not values
that can safely be guessed from the declaration's numbered casillas.

## Shipped boundary and refusal

The loaded `220/2024` revision selects only 2024 annual period `0A`, declares
the same 2024 record-design source, and records `authority_grade =
"applicability"`. It does carry the extensive reviewed casilla corpus, but
declares no export layout. Its application links identify the export surface
without claiming that the surface can produce a filing artifact.

The derived capability worklist reaches the producer-vocabulary check after
the 2024 source interval and casilla-surface checks. Its predicate constructs
the required namespace as `m{modelo.id}.`; a direct enumeration of
`FilingProducerKey` on 2026-08-24 returned `()` for the `m220.` prefix. The
worklist consequently refuses the revision because a semantic map cannot name
the non-casilla address, code, activity, representation, and repeated-group
facts without both a typed key and a live application producer behind it.

`FilingProducerKey` is a closed cross-layer contract whose values are supplied
only through the filing producer snapshot. Adding strings solely because the
design prints fields would create a design-only shell. Existing Modelo 200
keys are not a substitute: legal and accounting overlap does not establish
identity, lifecycle, collection cardinality, or provenance for a
group-consolidation declaration.

**Disposition: Modelo 220/2024 is supported as a law-selected applicability
revision and has exact 2024 layout evidence, but its fileable boundary is
empty.** The existing refusal is correct and must stay visible until the
prerequisites below are independently completed.

## Owner and reconsideration

`W02.P04.S27` must enroll the source-and-provenance work in
`2026-08-22-source-casilla-integration-plan`. Before any `m220.*` vocabulary
is introduced, it must approve the actual group-consolidation filer population
and one typed, provenance-carrying lifecycle for every non-casilla fact the
2024 design needs. That includes representative or dominant identity, group
composition and repeated member rows, the relevant censo-reconciled facts,
contact and address facts, declaration/amendment evidence, and any payment or
refund facts. It must prove the producer snapshot refuses absent, stale,
misattributed, duplicated, or cross-group values.

Once those value owners are real, `W02.P04.S28` must enroll the official-layout
work in `2026-08-10-aeat-export-fragment-generator-authority-plan`: make a
complete reviewed semantic map and render profile from `aeat-dr-220-2024`,
preserve its composite variable closing, generate only through the canonical
publisher, and prove real 2024 emitted bytes at the official offsets. No
partial record tree, copied Modelo 200 layout, or compatibility writer is
authorized.

`W02.P04.S26` has no missing source-era acquisition to perform for this closed
2024 revision. It must, however, retain the authority-grade gate: filing grade
is reconsidered only after the value owners, full semantic map, generated
fragments, registry validation, and real byte evidence are complete and an
approved authority decision allows Cadrumo to make that bounded product claim.
This adjudication does not authorize a grade promotion, remote AEAT submission,
or reuse of the later 2025 design.

## Sources

- BOE-A-2025-12818, Orden HAC/657/2025, articles 1, 2, and 6 and Annex II,
  retrieved 2026-08-24: https://www.boe.es/eli/es/o/2025/06/21/hac657
- AEAT historic 200--299 record-design catalogue, which links 220/Ejercicio
  2024, retrieved 2026-08-24:
  https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/ejercicios-anteriores-modelos-200-299.html
- AEAT 2024 Modelo 220 record-design workbook, retrieved 2026-08-24:
  https://www3.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_200_299/archivos_24/DR220e24.xlsx
- AEAT Modelo 220 2024 completion instructions, retrieved 2026-08-24:
  https://sede.agenciatributaria.gob.es/static_files/Sede/Procedimiento_ayuda/GE02/Instrucciones/Instr_220_2024.pdf
- AEAT historic Modelo 220 filing surface, retrieved 2026-08-24:
  https://sede.agenciatributaria.gob.es/Sede/impuestos-tasas/impuesto-sobre-sociedades/modelo-220-is-r_____idacion-fiscal-devolucion_/presentacion-declaraciones-ejercicios-anteriores.html
- `src/cadrumo/_data/registry/aeat/legal/is.toml`
- `src/cadrumo/_data/registry/aeat/modelos/220/revisions/2024/`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_220/`
- `src/cadrumo/core/_filing_producer_key.py`
- `src/cadrumo/domain/calculations/registry/tests/test_filing_capability_worklist.py`
- `src/cadrumo/domain/calculations/registry/tests/test_record_design.py`
- `2026-08-14-registry-temporal-coverage-plan`
- `2026-08-22-source-casilla-integration-plan`
- `2026-08-10-aeat-export-fragment-generator-authority-plan`

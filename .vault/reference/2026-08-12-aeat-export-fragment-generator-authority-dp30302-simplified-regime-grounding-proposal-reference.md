---
tags:
  - '#reference'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:5482dfae750497cf5e6fc4c3293e9a7ecfdabcb68c1e50f066f3ec64043c23bb'
related:
  - "[[2026-08-12-aeat-export-fragment-generator-authority-dp30302-projection-declaration-deficit-audit]]"
---

# `aeat-export-fragment-generator-authority` reference: `dp30302 simplified regime grounding proposal`

## Summary

This document exists so an operator can decide two things that an agent must not decide alone:
which legal provisions may be added to the catalogue to ground the Modelo 303 DP30302
simplified-regime fields, and which grounding vocabulary a projection endpoint declaration
should cite. It is prose about what is missing. It deliberately contains no proposed catalogue
entry, no drafted corpus excerpt, no legal text authored for adoption and no review stamp.

The blocked work is the extension of the revision-owned projection endpoint declaration index
so that every official DP30302 anchor has a canonical typed home. That index currently declares
34 simplified endpoints per revision against 134, 130, 140, 142 and 142 nonnumbered DP30302
anchors across the 2023, 2024-early, 2024-late, 2025 and 2026 epochs. Roughly 108 anchors per
epoch, about 518 in total, have no admissible home. The measurement and its method are recorded
in the companion audit.

## Why the framework article is not enough

The simplified regime's framework is Ley 37/1992 article 123, which is present in the catalogue
and is bundled in the corpus. Read directly, it delegates rather than establishes. Its first
paragraph provides that in activities under the simplified regime the determination of the tax
amounts is carried out by the method of indices, modules or other objective parameters "que se
determinen reglamentariamente por cada actividad", and its second paragraph provides that the
modules used are those "determinados en virtud de las disposiciones reglamentarias
correspondientes".

So article 123 establishes the METHOD and fixes no number. Under the project's grounding rule a
value must cite the provision that establishes it, and citing the general framework article
alone is insufficient where a more specific provision fixes the number. The existing módulos
parameters and formulas in the Modelo 303 revisions currently carry `ley-37-1992:art-123` and
nothing else, which is the generic-default shape that rule names.

The establishing layer is the annual Orden's Anexo II, which is the IVA side of the yearly Orden
that develops the objective-estimation method for personal income tax and the special simplified
regime for VAT. Anexo I of the same Orden is the personal income tax side and is not the
authority for these fields.

## Field-class to provision mapping

The exists column reports whether a citable entry is present in the legal catalogue under
`src/cadrumo/_data/registry/aeat/legal/`, per ejercicio, as measured through the loaded
authority. It does not assert that a present entry is the CORRECT establishing provision for the
class; confirming that is part of what this document asks for.

| Field class (non-agricultural cohort) | Establishing layer | 2023 | 2024 | 2025 | 2026 |
| --- | --- | --- | --- | --- | --- |
| Módulo units and importe, 7 per slot | Anexo II per-activity module table | see vocabulary section | see vocabulary section | see vocabulary section | see vocabulary section |
| Cuota devengada por operaciones corrientes | Anexo II instrucción 1 / 2.1 | absent | absent | absent | absent |
| Índice corrector de actividad | Anexo II instrucción 2.2 | absent | present | present | present |
| Porcentaje de ingreso a cuenta, 1T/2T/3T | Anexo II instrucción 2.3.b | absent | partial | partial | thin |
| Importe del ingreso a cuenta, 1T/2T/3T | Anexo II instrucción 2.3.b | absent | partial | partial | thin |
| Porcentaje de cuota mínima | Anexo II instrucción 2.3.b | absent | partial | partial | thin |
| Cuota mínima | Anexo II instrucción 2.3.b | absent | partial | partial | thin |
| Reducciones | Orden disposiciones adicionales | absent | present | present | present |
| 4T cuotas soportadas por operaciones corrientes | Anexo II instrucción 3 | absent | absent | absent | absent |
| 4T resultado | Anexo II instrucción 3 | absent | absent | absent | absent |
| Cuota anual derivada del régimen simplificado | Anexo II instrucción 3 | absent | absent | absent | absent |
| Devolución de cuotas soportadas | Anexo II instrucción 3 | absent | absent | absent | absent |
| Actividad de temporada, día counts | Anexo II instrucción | absent | absent | absent | absent |

| Field class (agricultural cohort) | Establishing layer | 2023 | 2024 | 2025 | 2026 |
| --- | --- | --- | --- | --- | --- |
| Código de actividad | framework plus Anexo II table | present | present | present | present |
| Volumen de ingresos | framework, article 123 | framework only | framework only | framework only | framework only |
| Índice de cuota | Anexo II agricultural table | absent | absent | absent | absent |
| Cuota devengada | Anexo II agricultural table | absent | absent | absent | absent |
| Porcentaje and ingreso a cuenta | Anexo II instrucción | absent | absent | absent | absent |
| 4T cuota soportada and resultado | Anexo II instrucción 3 | absent | absent | absent | absent |

The starkest cell is the 2023 column. Its Orden, `orden-hfp-1172-2022`, has exactly ONE catalogue
entry, `orden-hfp-1172-2022:art-4`, and no Anexo II instruction entries at all. The other three
ejercicios carry between 6 and 13 entries each. Whatever is decided for the other years, 2023
needs its Anexo II layer built from nothing.

Catalogue entries present today, for reference. Ejercicio 2023, `orden-hfp-1172-2022`: `art-4`.
Ejercicio 2024, `orden-hfp-1359-2023`: `anexo-ii-instruccion-2-3-b-1`, `-b-2`, `-b-4`,
`anexo-ii-instruccion-2-3-incompatibilidades`, `art-4`, `da-1`, `da-5`, `da-6`,
`instruccion-2-2-a`, `instruccion-2-2-b`, `instruccion-2-3-b-3`. Ejercicio 2025,
`orden-hac-1347-2024`: the same IVA set plus `anexo-i-instruccion-2-1`, `-2-2`, `-2-3` and
`anexo-i-instruccion-3`, which are the personal income tax side. Ejercicio 2026,
`orden-hac-1425-2025`: `anexo-ii-instruccion-2-3-incompatibilidades`, `art-4`, `da-1`,
`instruccion-2-2-a`, `instruccion-2-2-b`, `instruccion-2-3-b-3`.

The bare-prefixed identifiers such as `instruccion-2-2-a` are the IVA side despite lacking an
anexo prefix in their id: their `corpus_ref` resolves to the Anexo II instruction anchor of the
same Orden. This was verified, not assumed, but the naming is a trap for the next reader.

## Unverified expectations, marked as such

The reglamentario layer that article 123 delegates to is Real Decreto 1624/1992. The catalogue
carries eight of its articles: 29, 30, 30-bis, 69, 71, 79, 80 and 81. None concerns the
simplified regime.

The expectation that the simplified regime is governed by articles in the 34 to 42 range of that
Reglamento is UNVERIFIED DOMAIN EXPECTATION and is recorded here as a guess, not a finding. It
has not been read. The bundled consolidated file `rd-1624-1992.html` is the enacting decree
rather than the Reglamento annex, and searching its extraction returns zero occurrences of
"índice corrector", "cuota mínima" and "actividades de temporada". No bundled normative file in
the corpus mentions "régimen especial simplificado" at all. Any article number in that range must
be confirmed against consolidated text before it is relied upon.

Where a numeric amount or rate is involved, the bundled corpus is preferred but not infallible
and the value should be cross-checked against live consolidated text. A consolidated payload
carries every historical version oldest first, so the last version is the operative one.

## The two-vocabulary question

This is the harder of the two decisions and it determines whether the missing-entry work is even
the right work.

Two grounding vocabularies are in play and they do not currently meet.

The first is the legal catalogue under `src/cadrumo/_data/registry/aeat/legal/`, whose
identifiers are what casillas, bindings and projection endpoint declarations cite in their
`legal_refs`, and which the semantic-map validator resolves against. An endpoint declaration can
only cite an identifier that exists here.

The second is the annual Orden extraction. The Modelo 303 annual Orden authority already carries
genuinely grounded module data: 49 activities per ejercicio for 2023 through 2026, each with an
activity code, an IAE epígrafe, per-module order and coefficient as exact decimals, a cuota
mínima percentage, and per-module `legal_refs` of the form
`orden-hac-1425-2025:anexo-ii-iva:<digest>` together with a source content digest. That data is
read from `src/cadrumo/_data/corpus/normatives/html/orden-hac-1425-2025.html.extracted.json` and
its siblings, through `src/cadrumo/core/_orden_anual_html.py` and
`src/cadrumo/domain/calculations/registry/_m303_orden_anual.py`.

The `anexo-ii-iva` identifiers appear nowhere in the legal catalogue. So the refs that already
ground the module coefficients cannot be cited by an endpoint declaration, even though they are
digest-anchored and per-activity precise, which is stronger grounding than most catalogue
entries carry.

Options, with what each costs. No recommendation is made.

The first option is to promote the Anexo II extraction anchors into catalogue entries, so the
existing per-activity, per-module refs become citable directly. This preserves the precision
already achieved and keeps one vocabulary. It costs a large number of new catalogue entries,
one per activity per year at minimum, on a human-reviewed filing-grade surface, and it makes the
catalogue partly machine-derived, which may conflict with the expectation that every entry is
individually reviewed.

The second option is to have endpoint declarations cite a coarser catalogue provision, the
Anexo II instruction that establishes the rule, while carrying the digest-anchored extraction ref
through a separate sanctioned channel alongside it. This keeps the catalogue small and
hand-reviewed and preserves the digest trail. It costs a second reference channel on the
declaration schema, which is a schema change, and it splits one value's grounding across two
places, which a future reader must know to consult.

The third option is to ground endpoint declarations only at the instruction level and treat the
per-module coefficients as data validated by digest rather than as separately cited values. This
is the smallest change and needs the fewest new entries. It costs precision: the citation would
name the rule that establishes how a coefficient is applied without naming the coefficient's own
source line, which may be weaker than the grounding rule intends for a value that is itself a
regulatory number.

There may be a fourth shape none of these describe. The decision is the operator's.

## What is being asked

Confirm or correct the field-class to establishing-provision mapping above, in particular whether
Anexo II instrucción 1 or 2.1 is the correct authority for cuota devengada por operaciones
corrientes and whether instrucción 3 is correct for the annual regularisation classes.

Confirm the reglamentario articles that article 123 delegates to, replacing the unverified 34 to
42 expectation with read provisions.

Decide the vocabulary question above.

Authorise, as reviewed catalogue entries, whichever provisions the answers require. The blocked
work cannot proceed without them, and an agent must not author or self-stamp them.

Note that the 2023 ejercicio needs its Anexo II layer established from a single existing entry,
regardless of how the other questions are answered.

---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-26'
modified: '2026-07-26'
step_id: 'S15'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace declaracion-real-render-verification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S15 and 2026-07-26-declaracion-real-render-verification-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Populate form_number on the seventeen remaining inert blank-box guards across nine modelos, M180 and M193 and M349 fichero-BOE targets plus seven decl.ejercicio targets, a live fabrication-producing defect and ## Scope

- `src/cadrumo/_data/registry/aeat/modelos` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Populate form_number on the seventeen remaining inert blank-box guards across nine modelos, M180 and M193 and M349 fichero-BOE targets plus seven decl.ejercicio targets, a live fabrication-producing defect

## Scope

- `src/cadrumo/_data/registry/aeat/modelos`

## Description

- Re-derive the unguarded target set from the loaded registry rather than from the prior report.
- Establish what evidence could ground a printed box number for modelos that have no specimen.
- Populate form_number wherever AEAT's own published text states the number.
- Classify what remains, and measure whether it is the same defect.

## Outcome

Seventeen unguarded targets confirmed independently across nine modelos, matching the count reported. Seven are now armed and ten remain, split into two unlike problems.

The bundled AEAT instructions state printed box numbers directly, which is admissible authority rather than an inference from a diseno positional range. instr_mod_349 names Casilla 01 through 04 against their labels, and modelo-180-ayuda-resumen-datos names Casilla01 through 03. form_number is populated on those seven casillas and the guard arms for all of them, with no specimen required.

Modelo 180's own binding already cited that same file, carrying "Casilla01 Numero total de perceptores relacionados" as required_text. The evidence had been in the registry since the binding was authored; it had simply never reached the field the parser reads. That is worth noting because it means the blocked-on-evidence framing was too pessimistic: the first place to look for a printed box number is what the registry already cites.

Modelo 193's three targets are genuinely blocked. Its two bundled instruction files state no box numbers and it has no specimen. Its casilla structure is identical to Modelo 180's, which makes inferring 01/02/03 tempting and inadmissible; that inference is the one this line of work exists to refuse.

The seven decl.ejercicio targets are a different defect and a milder one. Measured across the whole estate, 281 targets carry a value_kind and exactly seven disagree with their own casilla's declared data_type: value_kind is amount while the casilla declares data_type year. The other 274 are coherent. So this is one systematic mistake repeated for a single casilla concept, not estate-wide rot.

Its severity is lower than the other ten. Those casillas are required, so a blank ejercicio is a malformed document rather than a legitimate optional blank, and the blank-box hazard is largely theoretical there. It is a type-coherence defect worth correcting, not a live fabrication path.

## Notes

The decl.ejercicio correction was deliberately not attempted here. Changing value_kind from amount to text changes the extracted type from Decimal to str, the domain filing protocol documents these casillas as plain integers, and five test modules assert on them. That is a typed-boundary change with real blast radius and it deserves its own scoped work rather than an opportunistic edit; it is tracked separately.

One claim was withdrawn during this work. An earlier pass reported Modelo 349's casilla 03 as mislabelled, its label appearing identical to casilla 01's. It is not: the label reads "Numero total de operadores intracomunitarios con rectificaciones" and the probe had truncated it at 44 characters. The registry is correct and the finding was an artefact of the instrument.

Registry and declaracion suites: 3265 passed, 1 failed. The failure asserts on an empty-string source_ref literal originating in a reconcile module this work never touched, proven pre-existing rather than assumed so.

The semantic code index remained truncated throughout, roughly 1027 chunks against roughly 4546 files while reporting itself healthy. Every claim here rests on loading the registry through the authority or on reading bundled corpus text.

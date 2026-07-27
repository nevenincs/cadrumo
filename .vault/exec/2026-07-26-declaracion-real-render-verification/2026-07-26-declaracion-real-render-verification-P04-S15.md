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

The decl.ejercicio correction was deliberately not attempted here, and the reason given was wrong.

CORRECTED 2026-07-27. This record argued the change was a typed-boundary change with real blast radius, citing the domain filing protocol documenting these casillas as plain integers and five test modules asserting on them. An independent trace of every production consumer found the extracted casilla value has none. Reconcile and verify both read a separate top-level declaracion.ejercicio string populated by template detection, not the casilla-keyed value; the calculation-side filing_year binding independently synthesizes its own value from the work unit's known year; and none of the seven affected modelos are reconcile-enrolled. The only consumer of the specific extracted entry is the parser-boundary tests.

So it is a contained fix: flip value_kind to text, update the test assertions. The protocol prose I cited describes a different field. Declining it was still the right call at the time, since the blast radius was unmeasured and I said so, but the stated reason did not survive measurement and should not be repeated.

One claim was withdrawn during this work. An earlier pass reported Modelo 349's casilla 03 as mislabelled, its label appearing identical to casilla 01's. It is not: the label reads "Numero total de operadores intracomunitarios con rectificaciones" and the probe had truncated it at 44 characters. The registry is correct and the finding was an artefact of the instrument.

Registry and declaracion suites: 3265 passed, 1 failed. The failure asserts on an empty-string source_ref literal originating in a reconcile module this work never touched, proven pre-existing rather than assumed so.

The semantic code index remained truncated throughout, roughly 1027 chunks against roughly 4546 files while reporting itself healthy. Every claim here rests on loading the registry through the authority or on reading bundled corpus text.

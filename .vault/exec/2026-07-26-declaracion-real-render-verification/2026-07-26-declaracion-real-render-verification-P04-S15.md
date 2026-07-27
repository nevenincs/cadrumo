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

The seven decl.ejercicio targets are a different defect and a milder one. They declare value_kind amount while their casilla declares data_type year.

CORRECTED 2026-07-27. This paragraph originally read that 281 targets carry a value_kind, that exactly seven disagree, and that the other 274 are coherent. Withdraw all three figures and the conclusion drawn from them.

Two later sweeps returned four and 114 for what was nominally the same question, and the disagreement is not about the registry. It is about three rules none of us stated. POPULATION: 281 against 478, because the sweeps enumerate different target sets. EQUIVALENCE: every sweep including the supposedly naive one silently treated amount and money as compatible, and the truly unqualified rule returns 371. DISCRIMINATION: whether year is distinct from integer, and enum from text, changes the answer and was never declared.

So the original claim was not a measurement of the registry, it was a measurement of one unstated rule-set, presented as a property of the estate. The follow-on claim that this was one systematic mistake rather than estate-wide rot does not survive either: under one stated equivalence the residual is 114 rows across 39 distinct triples and at least eight discrimination axes.

This record is corrected because a corpus consistency sweep caught it standing while the ADR that inherited the same figure had already been corrected. The figure originated here, so leaving it would have left the retracted version as the apparently authoritative source.

Its severity is lower than the other ten. Those casillas are required, so a blank ejercicio is a malformed document rather than a legitimate optional blank, and the blank-box hazard is largely theoretical there. It is a type-coherence defect worth correcting, not a live fabrication path.

## Notes

The decl.ejercicio correction was deliberately not attempted here, and the reason given was wrong.

CORRECTED 2026-07-27. This record argued the change was a typed-boundary change with real blast radius, citing the domain filing protocol documenting these casillas as plain integers and five test modules asserting on them. An independent trace of every production consumer found the extracted casilla value has none. Reconcile and verify both read a separate top-level declaracion.ejercicio string populated by template detection, not the casilla-keyed value; the calculation-side filing_year binding independently synthesizes its own value from the work unit's known year; and none of the seven affected modelos are reconcile-enrolled. The only consumer of the specific extracted entry is the parser-boundary tests.

So it is a contained fix: flip value_kind to text, update the test assertions. The protocol prose I cited describes a different field. Declining it was still the right call at the time, since the blast radius was unmeasured and I said so, but the stated reason did not survive measurement and should not be repeated.

One claim was withdrawn during this work. An earlier pass reported Modelo 349's casilla 03 as mislabelled, its label appearing identical to casilla 01's. It is not: the label reads "Numero total de operadores intracomunitarios con rectificaciones" and the probe had truncated it at 44 characters. The registry is correct and the finding was an artefact of the instrument.

Registry and declaracion suites: 3265 passed, 1 failed. The failure asserts on an empty-string source_ref literal originating in a reconcile module this work never touched, proven pre-existing rather than assumed so.

The semantic code index remained truncated throughout, roughly 1027 chunks against roughly 4546 files while reporting itself healthy. Every claim here rests on loading the registry through the authority or on reading bundled corpus text.

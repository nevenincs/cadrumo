---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-26'
modified: '2026-07-26'
body_hash: 'sha256:a90a0f59897b84c55a9c107c44ed514fe724970e15ce48c6d4fb7634f4f733d9'
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

## Re-verified and closed, 2026-07-28

Confirmed at HEAD rather than inherited, and the blocked state is now enforced rather than recorded in prose. The Step is closed on that basis.

The seven are armed in committed history, not merely in a working tree, checked by reading the files out of HEAD directly. That distinction matters here because a working tree carries peers' uncommitted work and would have shown the same result either way.

Modelo 193 remains blocked and no number was invented. The sweep behind that negative was widened and its instrument was corrected. This record previously said "two bundled instruction files"; there are nine Modelo 193 files across the diseño-de-registro and instruction trees, and the word "casilla" appears in none of them. One of them, the nota informativa, has no extracted-text sibling and had never been read at all -- 49,009 characters were extracted from it directly, with zero occurrences.

The first version of that sweep was unsound and would have produced the right answer for the wrong reason. It searched only markdown extractions, and Modelo 180's evidence -- the sweep's own precedent -- lives in HTML. It would therefore have "confirmed" no box numbers exist for Modelo 180 either. The instrument was validated against Modelo 180 first, where it correctly finds Casilla01 through 03, and only then was the Modelo 193 negative accepted. A clean grep is not evidence until the tool is shown to find the thing where it exists.

The blocked set is now asserted rather than described. A gate walks the estate and requires the unguarded monetary target set to equal exactly the three Modelo 193 rows, so a newly-added unguarded target fails instead of shipping silently, and arming Modelo 193 later also fails -- closing an evidence gap should be a deliberate edit, not a quiet behaviour change. The seven armed values are pinned against the AEAT documents that state them rather than against the registry, so the assertion checks the registry instead of restating it. Both directions were confirmed by mutation: removing one form_number flips both assertions, and the registry was restored byte-exactly.

The scope line names the registry tree only, and the gate lands in the declaracion adapter tests instead. The registry half of this Step was already complete; what was left was making the blocked state survive, and a record that only the vault holds is the thing this campaign has repeatedly found going stale.

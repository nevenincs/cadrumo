---
tags:
  - '#audit'
  - '#docs-terminology-search'
date: '2026-07-27'
modified: '2026-07-27'
related:
  - "[[2026-07-27-docs-terminology-search-modelo-concept-grounding-reference]]"
---

# `docs-terminology-search` audit: `legal ref attribution`

## Scope

Two results from grounding the 43 unenrolled modelo concepts that reach past the
Handbook and into the registry's legal grounding. Neither is a terminology
problem; both surfaced because someone finally read what the cited provisions
actually say.

## Findings

### citation-attribution-unchecked | high | the evidence gate proves presence, never ownership

Modelos `187`, `188` and `194` each declare `orden-eha-3377-2011:art-1` as their
legal grounding. That article approves a different form. Verified independently
by de-tagging the bundled corpus file: the approving sentence reads "Se aprueba
el modelo 193, Declaración resumen anual de retenciones e ingresos a cuenta sobre
determinados rendimientos del capital mobiliario", and "modelo 193" occurs 37
times against one occurrence of `187` and two each of `188` and `194` — which
appear only as scope carve-outs, naming rentas to be declared on those forms
*instead of* on 193.

`296` carries the same shape against `orden-hac-56-2024:art-1`, whose text
concerns "El anexo II, modelo 123".

The evidence gate passes all four, and is right to by its own contract: it
confirms a `required_text` phrase is present in the cited corpus file. It has no
notion of whether the provision BELONGS to the modelo citing it. So the gate is
not broken — it is narrower than it reads, and four filing-grade citations sit
inside that gap.

This is the tautology the grounding rule already warns about, one level up.
`legal-grounding-verifies-bundled-authoritative-corpus` records that a
self-authored `required_text` validates internal consistency rather than BOE
faithfulness. Here the text is faithful and the ATTRIBUTION is wrong, which no
phrase check can catch.

A candidate gate exists and is cheap: for a provision whose `required_text`
carries an approval phrase, assert the modelo's own number appears in the same
entry set. That rule already discriminated correctly in the grounding pass — it
found these four, and its first version wrongly demoted `848`, whose approval
phrase and form number are separate `required_text` entries, so it must read the
entries jointly rather than per-phrase.

### calendar-scope-is-not-glossary-scope | medium | a recommendation declined, and why

The grounding pass recommended excluding `145` from the Handbook because it is a
member of `OUT_OF_SCOPE_OBLIGATIONS`, whose recorded reason reads "local IRPF
payer communication, not an AEAT filing/calendar obligation".

Declined. `OUT_OF_SCOPE_OBLIGATIONS` is a CALENDAR taxonomy: it answers which
obligations the deadline engine schedules. Using it as a glossary filter repeats
the precise category error corrected hours earlier in this same feature, where
the `Modelo` enum — a typing device — was serving as the concept source. A list
built to answer one question is not authority for a different one, and that is
true however sensible the entry looks.

The membership test also fails on its own terms. `M036` sits in the same list and
is a currently-enrolled, plainly taxpayer-facing concept; excluding on this basis
would retire it. And the grounding pass's own reasoning cuts the other way: it
argues, correctly, that a taxpayer who RECEIVES a certificate under `187` has
genuine reason to look the form up. A taxpayer who personally fills in a `145`
for their employer has more, not less.

## Recommendations

Correct the four mis-attributed citations, and treat that as legal-authority work
rather than a registry edit. `187`, `188` and `194` need their own approving
orden located in the bundled corpus, or their citation reduced to the framework
provisions with the approval claim dropped rather than left pointing at another
form's orden. Note that five further modelos — `117`, `126`, `128`, `220`, `296`
— carry only framework provisions with no approving text found in the bundle at
all, so the corpus may simply not hold what these citations need.

Add the approval-attribution gate, reading `required_text` entries jointly. It is
the only mechanical check that would have caught this, and the grounding pass
already demonstrated both that it discriminates and how it fails when written
per-phrase.

Do not filter Handbook concepts on `OUT_OF_SCOPE_OBLIGATIONS`. If a
glossary-scope exclusion is wanted for a specific form, it needs its own declared
reason on the concept, not a borrowed one from the calendar.

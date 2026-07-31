---
tags:
  - '#audit'
  - '#docs-terminology-search'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:cd1ad5c659c823e6f56e70959bc9fa9c7f54ecbc9036e6fc8d2e9083374c30ce'
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

### correct-provisions-identified-not-bundled | high | the right ordenes are nameable, and their text is absent

The corpus was searched for the provision that actually approves each of the
three mis-attributed modelos. None is bundled, and the search says so precisely
rather than returning nothing.

Every bundled file that appears to approve `187`, `188` or `194` is CITING the
original in the standard Spanish legal form — "la Orden de 4 de septiembre de
2014, por la que se aprueba el modelo 187, se modifica…". A pattern that allowed
any text between "modelo" and the number returned nine files for `187`, which is
impossible for a form approved once; reading the matched sentence rather than
counting the matches is what exposed it. A tightened check confirms no bundled
file carries the approval as its OWN operative text for any of the three.

The citations do name the originals unambiguously:

- `187` — Orden of 4 September 2014
- `188` — Orden of 17 November 1999
- `194` — Orden of 18 November 1999

So this is not a research problem any more, it is a corpus-acquisition one. The
provisions exist, they are identified, and grounding these three citations
requires bundling their text. Until that happens the citations cannot be
corrected honestly: replacing one unverifiable reference with another the corpus
cannot check would satisfy the evidence gate while repeating the defect, which is
the specific failure `legal-grounding-verifies-bundled-authoritative-corpus`
exists to prevent.

### the-complete-acquisition-list | high | eight ungrounded modelos, resolved into three distinct causes

`345` is now grounded and needed no acquisition at all: its citation was correct
and only its pin was loose, carrying the bare "Se aprueba el modelo" with no form
number, so the evidence gate was confirming that SOME form is approved rather
than that `345` is. Corrected against the corpus text and proven to bite.

The remaining eight resolve into three causes, each established by reading the
approval sentences rather than by counting matches.

| Modelo | Approving provision | Bundled? |
|---|---|---|
| `187` | Orden HAP/1608/2014, de 4 de septiembre | no |
| `188` | Orden de 17 de noviembre de 1999 | no |
| `194` | Orden de 18 de noviembre de 1999 | no |
| `128` | Orden de 17 de noviembre de 1999 | no |
| `296` | Orden EHA/3290/2008, de 6 de noviembre | PARTIAL — see below |
| `117` | not named anywhere in the bundle | — |
| `126` | not named anywhere in the bundle | — |
| `220` | not named anywhere in the bundle | — |

`296` is the instructive one and its own sub-finding. That orden IS bundled, and
modelo `216` is verified against it — so the obvious reading is that `296` should
ground there too. It does not: the bundled file is a **1385-byte excerpt carrying
only articles 1 and 4**, both about `216`, and "modelo 296" occurs zero times in
it. The orden approves both forms; the excerpt covers one.

That trap generalises past this case. A `corpus_ref` pointing at a thin excerpt
makes a provision look ABSENT when it is merely out of frame, and the grounding
pass already counted 48 of 136 entries sitting on excerpts under 1500 characters.
Anyone concluding "the corpus does not contain this" from a failed search must
first check whether the file is the provision or a slice of it.

A mechanical sweep for the shape was attempted and produced nothing usable, which
is recorded so it is not rebuilt. Checking whether each cited article appears in
its own corpus file returns seven candidates, and six are artefacts of the
naming convention: a per-article excerpt such as
`orden-hac-2572-2003-art-1.html` carries the article in its FILENAME and opens
"Primero. Aprobación del modelo…", using an ordinal rather than "Artículo 1", so
the article is the file and cannot be found inside it. The seventh is a
211,000-character full orden where the missing token is more likely a casilla
than an article.

The `296` case was not of that shape anyway. Its cited article IS present; what
is absent is a DIFFERENT article approving a different form, which no
"is the cited article here" check models. Detection would need the excerpt's
coverage compared against the full provision, and the full provision is exactly
what the bundle lacks — so the check cannot be built from bundled data alone.

Two probe errors are recorded because both nearly became findings. A pattern
allowing 40 characters between "modelo" and the number reported nine files
approving `187`, which is impossible for a form approved once. And a window
regex reaching backwards for the nearest "Orden ..." attributed EHA/3290/2008 to
`296` from a sentence about a different clause — right conclusion, wrong
evidence, and it would have been quoted as proof. Reading the matched sentence
corrected both.

### acquisition-is-specified-and-proven-feasible | high | three documents, four modelos, identified and verified

The acquisition is no longer open-ended. Each missing provision is identified by
BOE number, retrieved from the official source, and confirmed to approve its
modelo in its OWN operative text rather than by citing a prior orden.

| BOE id | Orden | Approves | Verified operative text |
|---|---|---|---|
| `BOE-A-2014-9225` | HAP/1608/2014, de 4 de septiembre | `187` | "Artículo 1. Aprobación del modelo 187 y de los diseños físicos y lógicos. 1. Se aprueba el modelo 187, «Declaración informativa de acciones o participaciones…»" |
| `BOE-A-1999-22372` | de 17 de noviembre de 1999 | `128`, `188` | "se aprueban los modelos 128, en pesetas y en euros, de declaración-documento de ingreso y los modelos 188, en pesetas y en euros, del resumen anual…" |
| `BOE-A-1999-22309` | de 18 de noviembre de 1999 | `194` (with 123, 193) | approves modelos 123 and 193 alongside 194 |

Three documents therefore resolve FOUR of the eight ungrounded modelos, because
two of them approve a family rather than a single form. Each was located by
searching the official gazette for the approval language the bundled corpus
already quoted — so the corpus's own citations were accurate all along; what was
missing was the cited text, not the citation.

TWO CONTRACTS ANYONE DOING THE WIRING MUST NOT GET WRONG.

The retrieved bytes are valid UTF-8 and decode correctly. A first read rendered
"declaración" with a replacement character, which looks exactly like a
mis-encoded download and invites re-encoding the file to "fix" it. It was the
console, not the data: the same bytes decode cleanly as UTF-8 and contain
"declaración-documento", while ISO-8859-1 decodes without error and produces the
WRONG string. Re-encoding would have corrupted the text while appearing to
repair it, and `required_text` authored from the corrupted version would then
have matched its own corruption — a green gate over a fabricated corpus.

The bundled convention is an EXCERPT, not the whole document. Existing files run
from a few hundred bytes to full ordenes, and the thin ones are what produced the
modelo-296 trap recorded above. Whoever extracts these must state which articles
the excerpt covers, because an excerpt that silently omits an article makes a
real provision look absent.

WHAT WAS DELIBERATELY NOT DONE. The registry wiring — corpus files, legal
entries, and the `legal_refs` swap on four modelos — is not attempted here. It is
mechanical now, but it is filing-grade legal data behind a validator that fails
the whole registry load on an inconsistency, and the project rule requires an
agent-prepared legal entry to carry honest `reviewed_by` provenance pending
operator re-stamp rather than being stamped reviewed. Doing it carefully is worth
more than doing it quickly, and the unknown that made it hard is now gone.

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

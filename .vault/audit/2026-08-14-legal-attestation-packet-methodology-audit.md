---
tags:
  - '#audit'
  - '#legal-attestation-packet-methodology'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:453bfb81dd4b4e149fdd06325c3539b4556603673034d20deb3b3050676639ab'
related:
  - "[[2026-08-14-modelo-100-legal-attestation-review-batch-a-reference]]"
  - "[[2026-08-14-registry-campaign-sequencing-operator-attestation-ledger-audit]]"
---

# `legal-attestation-packet-methodology` audit: `Elision tautology: a required_text presence check is satisfiable by a document that shows nothing`

## Scope

This document exists to persist one durable methodology finding from authoring
the Modelo 100 legal-attestation review packet, Batch A, so it informs every
future batch and every future modelo's packet in this series, not just the one
where it was caught. Nothing under `modelos/100/**` or any other registry
directory was touched to produce this finding; it concerns the packet-authoring
process itself, not registry content.

## Findings

### elision-presence-check-tautology | high | a `required_text` presence check passed on a section reduced to a title and a placeholder

**Where:** the Batch A packet's first-draft section generator (a scratch
script, never committed), specifically its rule for trimming long bundled
corpus quotations to keep the document navigable across 49 sections.

**What happened:** the generator elided any paragraph that contained neither
the declared `required_text` phrase nor a numeric rate/amount/threshold
pattern, keeping only the article's title line and matching paragraphs. For a
short article whose sole `required_text` phrase is the article's own title
(`ley-35-2006:art-11`, "Individualización de rentas" — the title of Artículo
11 itself), every substantive paragraph of the article body matched neither
condition and was elided, leaving a rendered section consisting of the title
line followed by a single `[...]` placeholder. The packet's own printed
verification line — "`corpus_ref` resolves; every declared `required_text`
phrase is present in the quoted text" — was TRUE of this section, because the
phrase legitimately sits in the (retained) title. The check passed on a
section an operator could not use to verify anything against, because the
claim it exists to check was never in the elided body to begin with — the
title matched by construction, not by evidence.

**Why no gate caught it:** the packet's completeness assertion is a
`required_text`-presence check, the same mechanical check the registry build
itself runs (`normalise_corpus_text` substring test). That check answers "is
this phrase present," which is a real and correct question for the registry's
own build-time grounding gate — for that gate, the phrase's mere presence
IS the intended guarantee, and the underlying corpus file is independently
addressable if a reader wants more. It answers a different, weaker question
than what a REVIEW PACKET needs, which is "did the operator's evidence
survive," because a packet's whole purpose is to put the primary source in
front of a human who has no other copy in front of them at that moment. The
same check, correct in the registry, is a tautology when reused as the
packet's own quality gate: an anchor phrase sitting in a title will always
survive any elision rule that keeps titles, regardless of how much of the
body around it is removed. This was caught by eyeballing one generated
section before writing the file, not by any automated check, structural or
otherwise. Two prior packets in this series (Modelo 390, ten references;
Modelo 180/145/349, fifteen references) used broadly the same generation
approach and could have shipped with this defect silently; both were checked
by hand at the time and neither happened to hit a short-article/title-anchor
case, which is closer to good fortune than to a verified absence.

**The fix applied, in the same session:** replaced the paragraph-level
keep/elide filter with a much narrower rule — elide ONLY the trailing BOE
amendment-history citation footer lines ("Se modifica...", "Se añade...",
"Texto añadido...", "Téngase en cuenta..."), which are pure metadata, never
carry a `required_text` phrase, and never state a rate or amount. Every
substantive paragraph of every article is now quoted in full, unabridged, in
all three packets published so far. The resulting Batch A document is
larger (~255KB across 49 sections) than an aggressively-trimmed version would
have been; that size is the correct trade for a packet an operator can
actually verify against.

**Is there a cheap structural signal that would have caught this
automatically, so future authors are not relying on eyeballing alone?**
Partially. Two candidate structural signals were considered:

- A minimum quoted-block length, or a maximum elision-to-retained-text ratio,
  per section. This would have caught the `art-11` case (a one-line body
  against a multi-paragraph elision) but is not a general guarantee: a
  genuinely short, one-paragraph article with no elision at all would also
  trip a naive minimum-length threshold as a false positive, and a
  sufficiently verbose elision comment could pad the ratio without adding
  evidence. It narrows the failure mode; it does not close it.
- Asserting that the retained (non-elided) text alone — not the full
  resolved unit — independently contains every `required_text` phrase,
  rather than checking the phrase against the full unit before elision is
  applied. This is the more precise fix and is what the applied remediation
  achieves BY CONSTRUCTION (elision only ever removes footer lines the
  phrases are never in), but it is a property of the elision rule's design,
  not a check that could be bolted onto an arbitrary elision strategy after
  the fact. A future author choosing a different, more aggressive elision
  strategy would need to re-derive this guarantee, not inherit it from this
  finding.

Stated plainly for the next author: this one is held by DISCIPLINE — quoting
verbatim in full except for a narrowly-defined, provably phrase-free footer
class — not by an automated check that would catch a departure from that
discipline. Any future change to how a packet trims long quotations should
re-ask this exact question before shipping: does the retained text alone,
independent of what was elided, still carry every claim the section makes
about it?

### numeric-flag-undercount-is-directional | high | a catalogue-field-only numeric scan fails in the dangerous direction, and it did so on every batch it was tried against

**Where:** the numeric rate/bracket/threshold flag computed for each Batch A
and Batch B reference — first as a scan of the legal catalogue's own
`required_text` and `notes` fields only, later corrected to also scan the
full bundled corpus text the reference resolves to.

**What happened, across the whole series so far:** the catalogue-field-only
method undercounted the true numeric population every single time it was
checked against the fuller method, never overcounted. On Batch A it missed
zero (34 both ways, because Batch A's OR-of-both-signals method was already
in place when that batch was characterised). On Batch B it missed six of
37 — `ley-35-2006:art-17` (a 100.000 euros disability-insurance-premium
ceiling), `art-25`, `art-30`, `art-31`, `art-37`, and
`real-decreto-ley-7-2024:art-11` (a 25 por ciento módulos reduction) — a
16% undercount on that batch alone, discovered only because building Batch B
required resolving every reference's full text anyway and it was scanned
while already in hand.

**Why the failure is structural, not incidental:** a `required_text` phrase
is chosen by whoever authored the catalogue entry to prove the citation
resolves to the right provision, and the cheapest, most reliable phrase for
that purpose is usually the article's own title or a short definitional
sentence — not the specific number-bearing sentence buried in the body. The
two are frequently different sentences in the same article. A scan that only
reads the phrases already selected for a DIFFERENT purpose (citation
identity) will systematically miss numbers that live elsewhere in the same
text, and it has no way to notice its own miss, because the phrases it
scanned really were present and really did prove the citation resolved —
the scan is not wrong on its own terms, it is answering a question adjacent
to the one being asked.

**Why the direction matters more than the size:** an undercount on THIS flag
specifically sends the operator into a bracket table, a threshold or a
percentage believing no live cross-check is needed, because the packet never
told them to make one. That is the unsafe direction for a project rule that
exists precisely because "the bundled corpus is preferred evidence but not
infallible on numbers" — a flag that fires when it should not costs a
reader a few extra minutes of BOE reading; a flag that fails to fire when
it should sends a self-attested transcription of a percentage or a euro
figure past the operator with no signal to slow down. The two references
named above are exactly the shape most worth catching: neither is
procedural, both are the kind of concrete figure an operator would sign off
on if the flag never appeared.

## Recommendations

Carry the "elide only the amendment-history footer, never interior
substantive text" rule forward unchanged into Batch C and any future
modelo's attestation packet in this series — it is what closes the elision
finding, not merely works around it.

Before authoring any future packet that reuses or modifies this elision
approach, re-verify by construction (not by spot-checking one section) that
every retained block independently contains its section's `required_text`
phrases, rather than trusting that eliding based on `required_text`
presence is sufficient — presence in the FULL unit and presence in the
RETAINED text are different properties, and only the second one is what a
reader can act on.

Always compute the numeric flag from the FULL resolved corpus text, OR'd
with (never replaced by) a catalogue-field scan, from the first batch of any
future packet — never as a first pass to be corrected later. The
catalogue-only method is not merely less precise; it fails in the direction
that costs the operator the most, and the size of its miss (zero on one
batch, six of 37 on the next) gives no advance warning of when it will bite.

---
tags:
  - '#reference'
  - '#legal-corpus-vintage'
date: '2026-08-10'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:c21887a96682392f42152a0a2a1c9a8e1aca3169069dae599b84cc4238e0e26d'
related: []
---
# `legal-corpus-vintage` reference: `required_text gate discrimination across the excerpt corpus`

Grounding for the decision on what a corpus excerpt's gate must be able to say.
Measured offline: no network, no assumption about redaction history. Generalises
the art-81 finding recorded in the sibling audit.

**Corrected on 2026-08-13, and the correction is structural rather than
arithmetic.** The instrument that produced the first measurement derived its
consolidated anchor from a form BOE does not use, so it compared a third of its
own population against the wrong provision or against nothing at all. Both the
denominators and the `art-163-*` triage candidate below are restated, each
beside the figure it replaces. The instrument has been rebuilt and committed as
`dev/audit/legal_excerpt_vintage_screen.py`; every figure in the "Re-measured"
section is reproducible by running it.

## Summary

    legal-catalogue entries                                   606
      every one carries a required_text gate                  606
      corpus_ref points at a per-article EXCERPT              261   (259 distinct files)
      corpus_ref points at a bundled CONSOLIDATED file        345

Three entries point at a `source.pdf.extracted.md` that does not exist at that
path. Separate small defect, not swept.

## Method, and the instrument that was withdrawn

Where a norm has BOTH a per-article excerpt and a bundled consolidated file, the
consolidated file's same-anchor unit is the current text. Split it into
clause-level chunks, count how many are absent from the excerpt, and ask whether
the entry's `required_text` phrases are still all present.

**A first instrument compared a 400-character PREFIX and is withdrawn.** It
classified the art-81 excerpt, proven divergent by hand the same day, as
matching: that excerpt's opening is current and every divergence sits later in
the article. A narrower question that answers identically. The replacement is
clause-level and passes both controls -- art-81 comes out divergent at 16/16
clauses absent, and the instrument does emit a caught verdict, so it
discriminates rather than always agreeing.

**The clause-level instrument is ALSO withdrawn, for a different defect.** Its
comparison was sound; its anchor derivation was not. Read the next section
before reading any ratio in this document.

## The denominator correction

**The comparable set was 104 of 137 ELIGIBLE entries. It was published as 104
of 261, and that figure is wrong.** 261 is the count of excerpt-backed entries
in total; 157 of them had no bundled consolidated counterpart and could not be
compared at all. Every ratio stated against 261 was therefore measured against
a denominator that silently excluded well over half its own population, and the
33 entries between 104 and 137 were excluded by a defect rather than by a
declared limit.

**The 3-of-72 catch rate is UNAFFECTED and must not be "corrected" too.** Those
divergences sit inside the comparable set, so both the numerator and the
denominator were measured on entries the instrument actually reached. The
grammar argument in the ADR rests on that ratio and stands.

**Why the 33 were lost, and it is one mapping rule with two surfaces.** Sidecar
anchors concatenate an article number with its Latin ordinal and carry no
separator -- `#a163octiesdecies`. The catalogue and the excerpt filenames use a
hyphenated form, dotted sub-article suffixes, year vintage suffixes, and
non-article words such as `apartado` and `disposicion final`. Nothing bridged
the two. Nine entries failed LOUDLY, because the derivation landed on a
neighbouring unit and reported total divergence against text that is perfectly
current. A further 24 failed SILENTLY, because the derivation resolved to
nothing and they dropped out of the comparison unnoticed -- among them the
dotted sub-articles of `ley-35-2006` art-68, an apartado pair in two ordenes,
and a `disposicion final unica`.

**It is not an ordinal problem, and that is the trap.** A fix scoped to Roman
ordinals is what the loud population invites, and it would have turned the nine
visible failures green while leaving all 24 silent ones exactly as they were.

**The deeper cause, measured after the fix.** BOE's anchors are POSITIONAL, not
semantic: in `ley-31-2022` the unit anchored `#a1-3` is titled "Artículo 11",
and in `ley-37-1992` the same `#a1-3` is "Artículo 163 sexvicies".
Canonicalisation strips the hyphen, so `#a1-3` and `#a13` collide on one key. A
numeric anchor is therefore not a sound derivation key for any multi-digit
article. The rebuilt screen leads with the excerpt's own title instead, and
cross-checks the resolved unit's heading against the excerpt's; a resolution
whose headings disagree is reported as `misresolved` rather than silently
compared.

## The `art-163-*` triage candidate is settled: NOT A FINDING

**Withdrawn:** the claim that the nine `ley-37-1992:art-163-*` entries report
100 per cent clause absence and 100 per cent excerpt-only phrases, and that this
is "as consistent with an anchor-mapping mismatch as with wholesale
supersession".

It was the anchor-mapping mismatch, and this is now hand-checked and
instrument-reproduced. `ley-37-1992:art-163-octiesdecies` and the consolidated
unit anchored `#a163octiesdecies` are VERBATIM IDENTICAL over the opening
operative sentence: same article, current text, no supersession. The 100 per
cent absence figure was the instrument reading article 163 itself.

Re-measured across the whole family, ten `art-163-*` entries now resolve to
their own anchors: seven at zero clauses absent, three at one or two clauses
absent out of thirteen to twenty. None is a supersession finding.

**What this does NOT establish.** The opening-sentence comparison is conclusive
for same-provision IDENTITY and is not a full-text comparison. A later-clause
divergence in any of the recovered entries remains possible. The claim is that
the instrument was lying about them, never that they are clean.

## Re-measured, 2026-08-13

Run over the corpus as bundled that day, while `P03.S05` was concurrently
landing newly acquired consolidated payloads -- so the population differs from
the first measurement in both directions, and re-running the screen is the only
way to read a current figure.

    excerpt-backed catalogue entries screened            228
      no consolidated counterpart (unmeasurable)           9
      unresolved                                           0
      misresolved (heading cross-check refused it)         1
      excerpt matches current                             89
      diverges, deliberately year-vintaged                15
      diverges, gate FIRES                                 9
      diverges, gate GREEN                               105

    comparable                                           218 of 228

**Of 129 measured divergences the gate catches 9**, 15 of them vintaged by
design. The totals reconcile against the input population by construction: a
resolution failure is now a reported verdict rather than a drop-out, and the
screen refuses to print a split whose counts do not add up.

**The recovered population is 32** under this corpus -- 11 that the old
derivation mis-resolved and 21 it resolved to nothing. Their verdicts: 13
matching current text, 17 diverging with the gate green, 2 diverging with the
gate firing. 27 of the 32 are verbatim over the opening operative sentence.

**The unmeasured population has collapsed from 157 to 9**, because the
acquisition step landed consolidated counterparts for most of it. That is
acquisition, not adjudication: `P03.S06` owns whether the newly reachable
entries' catch rate is consistent with the 3-of-72 already measured, and the
first re-measured figure above is materially different, which is exactly the
disconfirming observation that row was written to look for.

## Three populations

**Discriminating: at most 3, and the 32 are UNTESTED rather than clean.** A gate
over an excerpt that matches current has nothing to discriminate from, so it is
not evidence its phrases would catch a future drift.

**Drawn from invariant text: 69.** Confirmed independently by a second route
below.

**The tautology population: commit identity cannot measure it here.** A query
asking whether one commit introduced both the excerpt and its `required_text`
returned 260 different / 1 same, which reads as near-empty. It is an artefact:
256 of the 261 excerpt files were added by ONE bulk commit and the entries were
introduced across 13, so "different commit" is guaranteed by construction. A
near-zero from an instrument that could hardly have returned anything else is
not evidence of absence.

**A sound offline substitute for the same concern:** a phrase present in the
excerpt and ABSENT from the current consolidated article cannot have been drawn
from current law.

    all phrases in the excerpt-and-current INTERSECTION      84
    at least one phrase the excerpt alone contains           17
      of those, EVERY phrase excerpt-only                    10
    at least one phrase absent from the excerpt itself        3

These four counts were computed under the withdrawn derivation and are carried
unrevised. Treat them as indicative until the rebuilt screen is extended to the
phrase-provenance question, which it does not answer today.

## Two worked cases

**`ley-37-1992:art-122`, régimen simplificado.** Reported 20/20 clauses absent,
which looked like an anchor artefact. Checked by hand: same article, same title,
and the operative text differs from the first clause. The excerpt says the regime
applies to *"los sujetos pasivos del Impuesto sobre el Valor Añadido que reúnan
los siguientes requisitos"*; current law says *"las personas físicas y las
entidades en régimen de atribución de rentas en el Impuesto sobre la Renta de las
Personas Físicas"*. A different eligibility set, not a wording drift. **One of its
two gate phrases exists only in the superseded formulation**, so the gate is
actively pinning the excerpt to stale law rather than merely failing to notice
it. `art-124` shares the shape.

Both survive the rebuilt instrument: art-122 and art-81 each resolve to their
own anchor with identity confirmed and still come out divergent. That is the
control against over-reach -- a derivation fix that turned the `art-163-*`
family green while also greening these two would be agreeing with everything
rather than measuring anything.

**The vintaged excerpts behave CORRECTLY, contrary to a first reading.**
`art-52-2015`, `art-68-2018`, `art-52-2021`, `art-66-2021` and `art-23-2021` each
carry at least one phrase unique to their historical text, so those gates do pin
their intended vintage. An earlier claim that they do not is withdrawn.

## Unmeasured, and it is the largest population

**Withdrawn as of 2026-08-13:** the statement that "157 of the 261
excerpt-backed entries have no bundled consolidated counterpart, so there is no
offline oracle for them at all", and that this population outnumbers the
measured set. It was true when written. The acquisition step has since reduced
it to 9, and the unmeasured population is now the smallest of the three rather
than the largest.

## What this does NOT establish

- **That any excerpt is CORRECT.** A matching excerpt and consolidated file can
  be stale together. The test detects disagreement with the bundled current text,
  never agreement with the law.
- **Per-entry severity.** An excerpt is a fragment, so a high absent-clause count
  can mean legitimate scoping. The counts are triage signal. What is sound is the
  binary: the excerpt differs and the gate did not notice.
- **Anything about the 345 consolidated-backed entries**, which were compared
  against nothing because a consolidated file is its own current text.
- **That an entry reported as matching over its opening operative sentence is
  clean.** That comparison establishes same-provision identity, not full-text
  agreement.

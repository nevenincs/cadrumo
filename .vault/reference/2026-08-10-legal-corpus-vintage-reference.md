---
tags:
  - '#reference'
  - '#legal-corpus-vintage'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:b87c27e453f57270bf781bddc2c5e0ebfebe48e22ab6a6f676f42916e5073492'
related: []
---

# `legal-corpus-vintage` reference: `required_text gate discrimination across the excerpt corpus`

Grounding for the decision on what a corpus excerpt's gate must be able to say.
Measured offline: no network, no assumption about redaction history. Generalises
the art-81 finding recorded in the sibling audit.

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

## Result over the 104 comparable entries

    excerpt matches current                    32   nothing to catch
    diverges, gate FIRES                        3
    diverges, gate GREEN                       54
    diverges, deliberately year-vintaged       15   divergence by design

**Of 72 measured divergences the gate catches 3.**

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

**The vintaged excerpts behave CORRECTLY, contrary to a first reading.**
`art-52-2015`, `art-68-2018`, `art-52-2021`, `art-66-2021` and `art-23-2021` each
carry at least one phrase unique to their historical text, so those gates do pin
their intended vintage. An earlier claim that they do not is withdrawn.

## Unmeasured, and it is the largest population

**157 of the 261 excerpt-backed entries have no bundled consolidated
counterpart**, so there is no offline oracle for them at all. Neither clean nor
dirty here -- unmeasured, and outnumbering the measured set.

The nine `ley-37-1992:art-163-*` entries report 100 per cent clause absence and
100 per cent excerpt-only phrases. That is as consistent with an anchor-mapping
mismatch on Roman-ordinal article names as with wholesale supersession, and none
has been checked by hand. Triage candidate, not a claim.

## What this does NOT establish

- **That any excerpt is CORRECT.** A matching excerpt and consolidated file can
  be stale together. The test detects disagreement with the bundled current text,
  never agreement with the law.
- **Per-entry severity.** An excerpt is a fragment, so a high absent-clause count
  can mean legitimate scoping. The counts are triage signal. What is sound is the
  binary: the excerpt differs and the gate did not notice.
- **Anything about the 345 consolidated-backed entries**, which were compared
  against nothing because a consolidated file is its own current text.

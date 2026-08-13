---
tags:
  - '#exec'
  - '#legal-corpus-vintage'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:8e7b2d9fb265c8369a227b71e6f49ccd9e3e4443e81d13e919d58d60c5eb47b6'
step_id: 'S07'
related:
  - "[[2026-08-10-legal-corpus-vintage-plan]]"
---
# RESOLVED BY MEASUREMENT. Fix the anchor derivation generally, re-run over the full eligible population, and correct every coverage statement published against the wrong denominator

## Scope

- `.vault`
- `dev/audit/`

## Description

- Landed the excerpt-versus-consolidated divergence measurement as a durable maintainer screen at `dev/audit/legal_excerpt_vintage_screen.py`, following the shape of its sibling `dev/audit/legal_attribution_screen.py`: a screen rather than a pytest gate, with its measured limits and its rejected widening written into the module docstring.
- Rebuilt the anchor derivation generally rather than special-casing the shape that was noticed first.
- Made a resolution failure a reported verdict class, and made the summary refuse to print a split that does not reconcile against its input population.
- Re-ran over the full eligible population and recorded the corrected split.
- Corrected the denominators and the settled triage candidate in the reference and the ADR, each beside the figure it replaces.
- Proved the fix is load-bearing by reinstating the old derivation at run time from outside the repository, confirming the control flips, and restoring.

## Outcome

### The derivation, and why the obvious fix was refused

The row named the mechanism as one mapping rule with two surfaces, and that is right, but the surfaces are not the ones the loud population suggests.

BOE's sidecar anchors are POSITIONAL, not semantic. In `ley-31-2022` the unit anchored `#a1-3` is titled "Artículo 11"; in `ley-37-1992` the same `#a1-3` is "Artículo 163 sexvicies". The shared canonicaliser strips non-alphanumerics, so `#a1-3` and `#a13` collide on one key. A numeric anchor is therefore not a sound derivation key for ANY multi-digit article, and a fix scoped to Roman ordinals would have left that intact — it would have greened the visible failures and changed nothing else, which is the outcome the row exists to prevent.

The derivation now leads with the excerpt sidecar's own full TITLE, which cannot collide with a positional anchor, and falls back to a structural heading rebuilt from the catalogue's citation token. That token grammar covers the article family with Latin ordinals concatenated (`art-163-octiesdecies` to `a163octiesdecies`), dotted sub-article and vintage-year suffixes dropped as scope within the article, the disposición families spelled out as written ordinals, and an orden's numbered apartados spelled as masculine ordinals. Every lookup then goes through the one canonical primitive, `resolve_anchored_extracted_unit`; the module derives a key and never selects a unit itself.

Two rules earned their place by biting during authoring rather than by argument. A hyphenated narrower key `a6-3` was emitted, silently resolved `rdleg-1-2004:art-6.3` onto "Artículo 63", and is now refused with a regression pinning it. And five entries were being compared against a file bearing a norm's bare stem that is itself a single-article excerpt rather than a whole-norm consolidation; a unit-count precondition now excludes those, and the identity cross-check is what surfaced them.

### Every resolution is cross-checked

The resolved unit's own heading must name the provision the entry cites. This is the only safeguard against the anchor-precedence hazard, because the canonical resolver tries an exact anchor before a structural heading, and a positional anchor can therefore win against a correct key. One entry, `ley-31-2022:art-39`, is reported `misresolved` on that check: its excerpt is titled "Artículo 39. Modificación de la Ley 27/2014" while the consolidated norm's article 39 governs pension revalorisation. That is plausibly a mislabelled excerpt rather than a resolution defect, and it is left as a reported finding for a tax review rather than smoothed away.

### The corrected split

Measured over the corpus as bundled on 2026-08-13, while the sibling acquisition step was concurrently landing newly acquired payloads.

    excerpt-backed catalogue entries screened            228
      no consolidated counterpart (unmeasurable)           9
      unresolved                                           0
      misresolved                                          1
      excerpt matches current                             89
      diverges, deliberately year-vintaged                15
      diverges, gate FIRES                                 9
      diverges, gate GREEN                               105

    comparable                                           218 of 228

Of 129 measured divergences the gate catches 9, fifteen of them vintaged by design. The verdict classes are exhaustive over the input and the totals reconcile by construction.

### The recovered entries

Thirty-two entries under this corpus: eleven the old derivation mis-resolved and twenty-one it resolved to nothing. The row measured thirty-three on the smaller corpus it was written against, which the rebuilt instrument corroborates rather than contradicts — the population moved because the catalogue and the corpus both changed underneath it.

Their verdicts: thirteen match current text, seventeen diverge with the gate green, two diverge with the gate firing. Twenty-seven of the thirty-two are verbatim over the opening operative sentence.

The whole `ley-37-1992` art-163 family is recovered and settled. Ten entries now resolve to their own anchors — `art-163-octiesdecies` reaching `a163octiesdecies` and coming out at zero of seven clauses absent, opening sentence verbatim, identity confirmed. Seven of the ten are at zero clauses absent; the remaining three are at one or two clauses absent out of thirteen to twenty. None is a supersession finding. The hundred-per-cent absence figure was the instrument reading article 163 itself.

The twenty-one silent recoveries include every shape the row named: the five dotted sub-articles of `ley-35-2006` art-68, the apartado pairs in `orden-hac-2572-2003` and `orden-hac-3625-2003`, and the high-ordinal disposiciones of `ley-27-2014` and `ley-58-2003` whose BOE anchors degrade to bare positional forms and are reachable only through their written ordinal.

### The controls

`ley-37-1992:art-163-octiesdecies` comes out MATCHING at its own anchor, and `ley-35-2006:art-81` still comes out DIVERGENT with its identity confirmed. `ley-37-1992:art-122` likewise stays divergent. An instrument that turned the first green while also greening the other two would be agreeing with everything rather than measuring anything, so both are pinned as corpus-anchored regressions.

The anti-tautology proof was run from outside the repository, rebinding the derivation seams in one process so nothing tracked was edited. With the old derivation reinstated the octiesdecies control flips from matching to unresolved, and — the load-bearing half — the totals still reconcile at 228, because the lost entries land in an explicit unresolved verdict instead of vanishing. Restored afterwards; the control returns to matching.

### The coverage statements corrected

The comparable set was 104 of 137 ELIGIBLE entries. It had been published as 104 of 261, and 261 is the count of excerpt-backed entries in total, most of which had no consolidated counterpart to be compared against at all. Every ratio stated against 261 therefore carried a denominator that silently excluded a large part of its own population, and the 33 entries between 104 and 137 were excluded by a defect rather than by a declared limit.

The three-of-72 catch rate is UNAFFECTED and is flagged in both documents so a later reader does not correct it too: those divergences sit inside the comparable set, so both numerator and denominator were measured on entries the instrument actually reached. The ADR's grammar argument rests on that ratio and stands unchanged.

Corrected in the reference: the withdrawn clause-level instrument is now named as withdrawn alongside the earlier prefix instrument; a denominator-correction section states the 104-of-137 figure beside the 104-of-261 it replaces and gives the mechanism; the nine-entry `art-163-*` triage candidate is restated as settled and NOT A FINDING; the "157 of the 261 have no offline oracle" statement is marked withdrawn with its replacement figure and the reason it moved; a re-measured section carries the current split; and the four phrase-provenance counts are marked as carried unrevised from the withdrawn derivation.

Corrected in the ADR: the considerations bullet now says 104 of the entries the first instrument could compare, with an explicit denominator-correction bullet beside it; the unmeasured-population figure is stated as a moving number with a pointer to the reference rather than frozen; and the consequences section retires the `art-163-*` triage candidate explicitly, noting that the decision never depended on it.

### The limit, carried into both the code and the prose

The opening-operative-sentence comparison is conclusive for same-provision IDENTITY and is not a full-text comparison, so a later-clause divergence in any of the recovered entries remains possible. The claim is that the instrument was lying about them, never that they are clean. That sentence is in the screen's module docstring and in the corrected reference. The screen carries the further limit that even its clause-level count compares against the bundled consolidated file rather than against the law: a matching excerpt and a stale consolidated file agree with each other.

## Notes

**Left for the sibling row deliberately.** The re-measured catch rate is materially different from the three-of-72 already measured. That is the disconfirming observation `P03.S06` was written to look for, and adjudicating whether the first comparable set was representative belongs to that row. Recorded here without a remedy.

**A latent defect in shipped code, reported rather than fixed.** The shared anchor canonicaliser in `src/cadrumo/core/corpus_text.py` strips non-alphanumerics, so `#a1-3` and `#a13` collide on one key. Nothing filing-grade resolves against it today, because every entry with such an anchor cites a single-unit excerpt file where the collision cannot arise. Fixing it is a behaviour change on a legal-evidence path and needs its own row with its own gate work; the screen routes around it and reports the ambiguity rather than papering over it.

**Full-tree gate state at closing, triaged.** Three failures on the legal and corpus surface, none of them this Step's: the extraction-sidecar freshness pair and the unverified-anchor ratchet ceiling. All three sit on the 179 uncommitted corpus paths the concurrent acquisition step is landing, plus two newly added catalogue entries. Collection reported two errors under parallel workers; one is a peer's in-flight CLI overview refactor importing a symbol that does not exist yet, and the other collects cleanly when run alone, which is the backing share's known concurrent-I/O flake. Nothing under `dev/audit/` is read by any of them.

**Nothing under the corpus directory was written.** The screen reads whatever is bundled at run time with no baked-in file list, so the acquisition step's additions widen its population automatically rather than needing it re-edited.

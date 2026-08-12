---
tags:
  - '#plan'
  - '#legal-corpus-vintage'
date: '2026-08-10'
modified: '2026-08-12'
body_hash: 'sha256:7cf82c43208f3a9198f16cd4f5e1a38495f9043b7c9531d56590ac45de4f71d3'
tier: L2
related:
  - '[[2026-08-10-legal-corpus-vintage-adr]]'
  - '[[2026-08-10-legal-corpus-vintage-reference]]'
---

# `legal-corpus-vintage` plan

## Description

## Steps

### Phase `P01` - The negative clause

Give the gate a way to say a clause must be ABSENT, and make the failure message distinguish the two opposite defects.

- [x] `P01.S01` - Add an optional forbidden-text clause to the legal-catalogue entry schema alongside required_text, evaluated at registry build. The failure message names WHICH clause fired, because a missing required phrase and a present forbidden phrase diagnose opposite defects and one message conflates them; `src/cadrumo/_data/registry/aeat/legal/, src/cadrumo/domain/calculations/registry/`.
- [x] `P01.S02` - Prove the new clause bites and prove it does not over-reach in the same row. The refusal must fire on a document containing a forbidden phrase, and the CONTROL that decides closure is that every one of the 606 existing entries still loads unchanged, with the deliberately vintaged excerpts named explicitly because they legitimately contain text current law does not. Do not close on the refusal firing; `src/cadrumo/domain/calculations/registry/tests/`.

### Phase `P02` - Author the clauses that are already evidenced

Only two entries have a hand-checked divergence behind them. Author those and stop, rather than sweeping.

- [ ] `P02.S03` - Author the forbidden-text clause for ley-35-2006 art-81 in the same change as the corpus_ref repoint the sibling audit prepared, naming the repealed cotizaciones ceiling as text the cited document must not contain. This is the operator-stamped entry, so the authoring is prepared and the stamp is not an agent act; `src/cadrumo/_data/registry/aeat/legal/irpf.toml`.
- [ ] `P02.S04` - Author the forbidden-text clause for ley-37-1992 art-122 and art-124, naming the superseded regimen simplificado eligibility wording. Note before starting that one of art-122's two existing required_text phrases exists ONLY in the superseded formulation, so that phrase is itself part of the defect and removing it is part of the fix rather than collateral; `src/cadrumo/_data/registry/aeat/legal/`.

### Phase `P03` - Reach the unmeasured population

157 excerpt-backed entries have no offline oracle. This phase is mechanical acquisition, not adjudication.

- [ ] `P03.S05` - Acquire the redaction history for the 157 excerpt-backed entries that have no bundled consolidated counterpart, through dev/corpus/fetch_boe_normative.py and never by hand. Three traps are already measured and must be carried: act.php lists versions NEWEST first while the open-data article endpoint concatenates them OLDEST first, so a take-the-last rule is right for one and bundles repealed law for the other; `a fresh BOE payload is CRLF while .gitattributes declares eol=lf, so the extracted sidecar records a sha that no checkout reproduces unless the source is normalised to LF BEFORE extracting; and legal text must never pass through a shell. Read every written file back before trusting it; `src/cadrumo/_data/corpus/normatives/html/`.
- [ ] `P03.S06` - Re-run the clause-level divergence measurement over the newly reachable entries and report the split, without proposing a remedy. The disconfirming observation: if the newly measured population's catch rate differs materially from the 3-of-72 already measured, the 104 comparable entries were not representative and the ADR's premise needs re-examining rather than extending; `src/cadrumo/_data/registry/aeat/legal/`.
- [ ] `P03.S07` - RESOLVED BY MEASUREMENT, and the population is 33 rather than nine. The hand check this row asked for has been run on ley-37-1992 art-163 octiesdecies: the excerpt and the consolidated unit are VERBATIM IDENTICAL over the opening operative sentence, same article, current text, no supersession. The consolidated sidecar carries that unit anchored a163octiesdecies. So the hundred-per-cent clause absence was the instrument and not the law, and this triage candidate is settled as NOT A FINDING rather than as a finding deferred. THE MECHANISM IS ONE MAPPING RULE WITH TWO SURFACES, which is why the row widens. Sidecar anchors concatenate the article number and its ordinal with no separators, while the catalogue and the filenames use a hyphenated form, dotted sub-article suffixes, and non-article words such as apartado and disposicion final. Nothing bridges the two. The nine fail LOUDLY because the derivation lands on a neighbouring unit and reports total divergence against correct current text. A further 24 entries fail SILENTLY because the derivation resolves to nothing at all and they drop out of the comparison unnoticed, among them the dotted sub-articles of ley-35-2006 art-68, an apartado pair in two ordenes, and a disposicion final unica. IT IS NOT AN ORDINAL PROBLEM. A fix scoped to Roman ordinals, which is what the loud population invites, would leave all 24 silent failures exactly as they are while turning the visible ones green. Fix the DERIVATION and re-run, rather than special-casing the shape that happened to be noticed first. AND CORRECT THE COVERAGE STATEMENTS: the comparable set was 104 of 137 eligible entries, never 104 of 261, so every ratio published against 261 was measured against a denominator that silently excluded a third of its own population. The three-of-72 catch rate is unaffected because those divergences sit inside the comparable set. WHAT THIS DOES NOT ESTABLISH: the opening-sentence comparison is conclusive for same-article identity and is not a full-text comparison, so a later-clause divergence in any of the 33 remains possible. The claim is that the instrument was lying about them, never that they are clean; `.vault`.

## Parallelization

## Verification

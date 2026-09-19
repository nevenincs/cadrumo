---
tags:
  - '#plan'
  - '#legal-corpus-vintage'
date: '2026-08-10'
tier: L2
related:
  - '[[2026-08-10-legal-corpus-vintage-adr]]'
  - '[[2026-08-10-legal-corpus-vintage-reference]]'
modified: '2026-08-25'
body_hash: 'sha256:ff5594392d13674200efeb94e5dcebb73c6cf859693555e4f163bb30d134e10a'
---

<!-- RETIRED: S08, S09, S10, S11, S12 -->

# `legal-corpus-vintage` plan

## Description

Deliver the negative-clause schema, corpus acquisition and refusal controls,
and the clause-level vintage screen without overwriting operator-reviewed legal
attestations. Candidate legal corrections remain immutable evidence in the S03
and S04 execution records. The registry campaign's operator-attestation ledger
is the sole live owner of the outstanding art. 81, art. 122, art. 124, and
guarderia-scoping determinations. Retired S08 and S09 were a permanent human
queue and its dependent bookkeeping row, not executable implementation work.

## Steps

### Phase `P01` - The negative clause

Give the gate a way to say a clause must be ABSENT, and make the failure message distinguish the two opposite defects.

- [x] `P01.S01` - Add an optional forbidden-text clause to the legal-catalogue entry schema alongside required_text, evaluated at registry build. The failure message names WHICH clause fired, because a missing required phrase and a present forbidden phrase diagnose opposite defects and one message conflates them; `src/cadrumo/_data/registry/aeat/legal/, src/cadrumo/domain/calculations/registry/`.
- [x] `P01.S02` - Prove the new clause bites and prove it does not over-reach in the same row. The refusal must fire on a document containing a forbidden phrase, and the CONTROL that decides closure is that every one of the 606 existing entries still loads unchanged, with the deliberately vintaged excerpts named explicitly because they legitimately contain text current law does not. Do not close on the refusal firing; `src/cadrumo/domain/calculations/registry/tests/`.

### Phase `P02` - Author the clauses that are already evidenced

Only two entries have a hand-checked divergence behind them. Author those and stop, rather than sweeping.

- [x] `P02.S03` - Author the forbidden-text clause for ley-35-2006 art-81 in the same change as the corpus_ref repoint the sibling audit prepared, naming the repealed cotizaciones ceiling as text the cited document must not contain. This is the operator-stamped entry, so the authoring is prepared and the stamp is not an agent act; `src/cadrumo/_data/registry/aeat/legal/irpf.toml`.
- [x] `P02.S04` - AUTHORING ONLY, and the two halves diverge. Prepare the forbidden-text clause for ley-37-1992 art-122 as a candidate diff in the exec record and do NOT write it into the live registry file: both entries carry review_status reviewed and reviewed_by operator, so an agent editing corpus_ref, effective_from or required_text would silently change what that signature covers. Art-122 is preparable and its warning is now measured rather than assumed: of its two existing required_text phrases, volumen de operaciones is ABSENT from the text in force and PRESENT in the excerpt, so that phrase is part of the defect and removing it is the fix. Art-124 is NOT preparable as a negative clause and is escalated instead. The article in force is titled Ambito subjetivo de aplicacion and governs the regimen especial de la agricultura, ganaderia y pesca, while the entry's notes, required_text and the excerpt it cites all describe obligaciones formales del regimen simplificado. That is a wrong-provision defect, not superseded wording, and a clause saying the cited document must not contain libro registro would red the build without expressing it, because deciding which provision now carries the obligation is a tax review and a repoint of an operator-stamped entry. Record both dispositions in the exec record with the evidence; `src/cadrumo/_data/registry/aeat/legal/`.

### Phase `P03` - Reach the unmeasured population

157 excerpt-backed entries have no offline oracle. This phase is mechanical acquisition, not adjudication.

- [x] `P03.S05` - Acquire the redaction history for the 157 excerpt-backed entries that have no bundled consolidated counterpart, through dev/corpus/fetch_boe_normative.py and never by hand. Three traps are already measured and must be carried: act.php lists versions NEWEST first while the open-data article endpoint concatenates them OLDEST first, so a take-the-last rule is right for one and bundles repealed law for the other; `a fresh BOE payload is CRLF while .gitattributes declares eol=lf, so the extracted sidecar records a sha that no checkout reproduces unless the source is normalised to LF BEFORE extracting; and legal text must never pass through a shell. Read every written file back before trusting it; `src/cadrumo/_data/corpus/normatives/html/`.
- [x] `P03.S06` - Re-run the clause-level divergence measurement over the newly reachable entries and report the split, without proposing a remedy. The disconfirming observation: if the newly measured population's catch rate differs materially from the 3-of-72 already measured, the 104 comparable entries were not representative and the ADR's premise needs re-examining rather than extending; `src/cadrumo/_data/registry/aeat/legal/`.
- [x] `P03.S07` - RESOLVED BY MEASUREMENT, and the population is 33 rather than nine. The hand check this row asked for has been run on ley-37-1992 art-163 octiesdecies: the excerpt and the consolidated unit are VERBATIM IDENTICAL over the opening operative sentence, same article, current text, no supersession. The consolidated sidecar carries that unit anchored a163octiesdecies. So the hundred-per-cent clause absence was the instrument and not the law, and this triage candidate is settled as NOT A FINDING rather than as a finding deferred. THE MECHANISM IS ONE MAPPING RULE WITH TWO SURFACES, which is why the row widens. Sidecar anchors concatenate the article number and its ordinal with no separators, while the catalogue and the filenames use a hyphenated form, dotted sub-article suffixes, and non-article words such as apartado and disposicion final. Nothing bridges the two. The nine fail LOUDLY because the derivation lands on a neighbouring unit and reports total divergence against correct current text. A further 24 entries fail SILENTLY because the derivation resolves to nothing at all and they drop out of the comparison unnoticed, among them the dotted sub-articles of ley-35-2006 art-68, an apartado pair in two ordenes, and a disposicion final unica. IT IS NOT AN ORDINAL PROBLEM. A fix scoped to Roman ordinals, which is what the loud population invites, would leave all 24 silent failures exactly as they are while turning the visible ones green. Fix the DERIVATION and re-run, rather than special-casing the shape that happened to be noticed first. AND CORRECT THE COVERAGE STATEMENTS: the comparable set was 104 of 137 eligible entries, never 104 of 261, so every ratio published against 261 was measured against a denominator that silently excluded a third of its own population. The three-of-72 catch rate is unaffected because those divergences sit inside the comparable set. WHAT THIS DOES NOT ESTABLISH: the opening-sentence comparison is conclusive for same-article identity and is not a full-text comparison, so a later-clause divergence in any of the 33 remains possible. The claim is that the instrument was lying about them, never that they are clean; `.vault`.
- [x] `P03.S13` - Make the screen see the defect class the ADR is about. The divergence computation counts only clauses of the CURRENT text absent from the excerpt, so an excerpt carrying all of current law PLUS a surviving repealed clause classifies as MATCHES, whose docstring asserts there is nothing for a gate to catch. That is the exact shape the ADR's negative clause exists to express, and 89 entries are published under that verdict today while rd-1065-2007 art-25 demonstrably carries two operative lettered clauses absent from the current article. Count excerpt-side extra clauses alongside absent, carry the count on Finding, and stop MATCHES absorbing them. The MEASURED LIMIT paragraph states the opening-sentence limit and the bundled-corpus limit and must state this asymmetry too, because the MATCHES docstring makes a claim the instrument does not measure. Do not re-derive the verdict split by hand. The totals must still reconcile and the corpus-pinned controls must still resolve opposite ways; `dev/audit/legal_excerpt_vintage_screen.py, dev/audit/tests/`.
- [x] `P03.S14` - Refuse the version pile structurally, rather than resting on nothing pointing at it yet. The 58 acquired article payloads carry BOE's full redaction history by design, but the extractor folds every version into ONE undelimited unit with no fecha_vigencia attribution, and boe-a-1991-14392-a30-redacciones is ten versions in a single 15.8k-character unit. Any corpus_ref resolving there fuses repealed and current law, and a required_text presence check passes on REPEALED text, which is the trap the grounding rule states verbatim and the trap the S05 row names in its own heading. S06 handled it for the screen by reading the raw payload and reducing to the redaction in force, but the committed DATA is still a pile. Either split the article-endpoint extraction one unit per version carrying its fecha_vigencia, or refuse at registry build any corpus_ref resolving to a redacciones sidecar. Prove the refusal bites by breaking it on purpose from outside the repo; `dev/docs/preprocess/, src/cadrumo/domain/calculations/registry/, src/cadrumo/_data/corpus/normatives/html/`.
- [x] `P03.S15` - Close the three smaller review findings in one pass. The identity cross-check leads with the excerpt's OWN title and then compares the excerpt's heading against the unit that key selected, which is near-forced for 204 of 219 resolutions, while the docstring claims the resolved unit must name the provision THE ENTRY CITES, so either bind the catalogue citation token to the excerpt through the canonical resolver or correct the claim. The two dev screens each carry their own copy of the same catalogue walk, the same _LEGAL_DIR, the same byte-identical refusal and the same glob-to-tomllib-to-legal traversal, so hoist one loader and have the attribution screen project required_text off the body. And two wordings are false as written. main documents Always exits 0 while screen raises SystemExit on a missing catalogue, on zero corpus files and on an unreadable sidecar. norm_root returning None is commented as citing the consolidated file itself when it also means no prefix is bundled at all, which is the silent-drop class this campaign removed and is true by accident today at zero entries; `dev/audit/legal_excerpt_vintage_screen.py, dev/audit/legal_attribution_screen.py, dev/audit/tests/`.

## Parallelization

## Verification

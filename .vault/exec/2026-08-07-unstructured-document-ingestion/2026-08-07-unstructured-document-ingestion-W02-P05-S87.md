---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:7eafff7808b4bc91cd8a557d5f21998820d236582e638e0b3e3934ae57795d1e'
step_id: 'S87'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Compile the statutory legend vocabulary from RD 1619/2012 art. 6.1 mandated mentions as prompt data with the instruction to copy verbatim if printed and never to choose one, gated by extending the anti-drift literal scan so the legend set carries no hardcoded prose literal outside its single home, proven by mutation in both directions

## Scope

- `src/cadrumo/llm`

## Description

- Locate the mandated mentions in the bundled consolidated text of the invoicing
  regulation's article 6 rather than authoring them: the article puts each one in
  guillemets, so the vocabulary is extractable rather than transcribable by hand.
- Declare the seven phrases as typed rows in the IVA domain, each carrying the
  article letter that mandates it, the category it declares if any, and whether
  an invoice printing it should also carry a repercutido line.
- Render the phrases into the compiled prompt from that declaration, quoted, with
  the instruction to copy one if printed and an explicit refusal of the nearest
  match.
- Add the prose counterpart to the numeric literal scan, pointed at the
  registered template, and prove by mutation that it reds on a phrase planted
  there.

## Outcome

The vocabulary has one home, and its grounding is proven mechanically rather than
attested. The gate compares the declared phrases against the guillemet-quoted
mentions in the shipped corpus as SETS, in both directions, so a paraphrase, an
invention and a dropped mention each fail it. An author asserting "these are
verbatim" is exactly the claim that cannot be trusted about itself; this one can
be re-run by anyone holding the repository.

Three judgements are recorded because each could have gone the convenient way.

The exempt case is deliberately absent. Article 6.1.j fixes no phrase for an
exempt operation -- it requires a REFERENCE to the provision granting the
exemption, so a document may print any of several forms and no canonical string
exists to match. Authoring one would have manufactured a mandated mention the
regulation does not mandate, and matching against it would then look
authoritative while being a guess. Exempt operations are not derivable from a
legend and fall to the classifier's absent state.

Only one of the seven declares a category. That is the measured state of the law
rather than an unfinished table: the rest oblige a statement about the billing
arrangement or a special regime's accounting, and none fixes the operation's IVA
category on its own. The gate pins that sparseness by member, so a future row
claiming a category has to earn it from the regulation.

Matching is case-folded rather than variant-listed, because a list of spellings
would be a second vocabulary drifting against the first.

The prompt grew, and the growth is the ruling's trade: one more copy field
replaces a taxonomy the model had to reason over. A closed list offered as a
recognition aid is not a menu, and the difference is carried by the instruction
rather than left to inference.

## Verification

    pytest src/cadrumo/llm/tests/test_regime_legend_vocabulary.py -n0 -p no:randomly -q
    22 passed in 41.09s

Grounding confirmed directly against the shipped file before any gate was
written: every declared phrase present, and the declared set equal to the
corpus's quoted set.

Proven by mutation in both directions, each applied to an isolated export so no
tracked file changed.

Paraphrasing one declared phrase -- an accent dropped, nothing more:

    3 failed, 19 passed in 52.73s

Aiming the prose scan at an import-time snapshot instead of the registered
template:

    1 failed, 21 passed in 27.60s

The second is the one worth naming. It is the same trap the numeric scan was
already caught in: a control that proves the detector matches a string says
nothing about whether the gate reads the artefact that ships, and it passes
forever regardless of where the gate is aimed. The prose gate now carries a
control for the target as well as for the detector.

A third assertion records why the second scan exists at all, since it otherwise
reads as duplication of the first: a statutory phrase planted in the template
carries no digit, so the numeric scan reports clean on the very text the prose
scan rejects.

## Notes

No inference was run. No model was loaded and no request was issued, so nothing
here claims the enumeration improves what a low-tier model reads; it claims the
vocabulary has one grounded home and cannot silently acquire a second.

An earlier reading of this corpus concluded the bundled legal text was mutilated
and the reference dangling. That was wrong, and the cause is worth recording:
the shell pipeline used to inspect the files was mangling accented characters and
digit runs, so the corruption was in the instrument rather than in the corpus.
Re-reading the same files through Python showed the identifiers intact and the
referenced file present. The near-miss was a report of a fabricated
campaign-level defect, avoided only by checking a surprising result twice.

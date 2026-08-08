---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:b916479bceb71f41070dbba1a2ec45f7991f93430b2bdc27bd96e260e79d9b3a'
step_id: 'S223'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Fold diacritics in the regime-legend match

## Scope

- `src/cadrumo`

## Description

- Measure both blocking conditions before changing anything: the seven mentions yield seven distinct folded forms with no collision and no nesting, and every mention is four to nine words after folding.
- Add a normaliser folding case, whitespace and combining accents, mirroring the printed-country vocabulary's three normalisations and its reasoning, and stating why folding an accent is not the paraphrase the match refuses.
- Index the vocabulary by normalised mention and refuse the whole table when two provisions claim one form, adopting the country loader's shape rather than inventing one.
- Split the index build from the shipped table so the collision refusal is reachable with a supplied vocabulary, for the reason the country loader states: a check exercisable only through the bundled table is a check nothing proves.
- Keep containment on the full multi-word mention, and gate that behaviourally by asking the matcher whether a lone token matches rather than by counting words.
- Gate what folding does beyond accents, on the shapes the transform actually rewrites.

## Outcome

A document whose text layer or OCR dropped the accent now derives the regime the issuer printed, so a contradiction can fire on it. The measured conditions are recorded rather than assumed: seven entries to seven folded forms, no nesting, shortest mention four words.

The transform rewrites more than accents, because it is compatibility-decomposing: ligatures, fullwidth forms, circled digits and the ordinal indicator all change under it. Greek and Cyrillic only case-fold and are not transliterated to Latin, and the Turkish dotless i is left alone, so none of that can assemble a Spanish mention. No hazard input matches any mention, and that is asserted on the shapes that change most rather than on Latin text alone.

## Verification

    uv run --no-sync pytest src/cadrumo/domain/iva/tests/test_regime_legend_diacritic_folding.py -n0 -q
    14 passed in 1.05s

    uv run --no-sync pytest src/cadrumo/domain/iva/tests src/cadrumo/application/ledger/tests -n0 -q -m unit
    1922 passed, 26 deselected, 16 warnings in 150.91s (0:02:30)

    uv run --no-sync ty check src/cadrumo/domain/iva/_legend_derivation.py
    All checks passed!

Proved to bite by substituting the normaliser from outside the repository, each arm reporting how many times the substitute was reached:

    [MUT no diacritic folding]: normaliser called 9x -> REDS
    [MUT token-level folding ]: normaliser called 5x -> REDS
    [MUT all entries collide ]: normaliser called 2x -> REDS
    [CONTROL real normaliser ]: -> PASSED

The two over-folding arms red through the collision refusal rather than through the assertion each was aimed at, which is the refusal doing its job: collapsing distinct mentions is exactly what it exists to catch. So the lone-token assertion was proved separately against a matcher loosened to compare tokens, where it reds naming the token that matched.

## Notes

The legend normaliser and the printed-country one now have identical bodies, both being case-fold, accent-fold and whitespace-collapse for matching a printed phrase against a closed vocabulary. A third nearby folding is NOT substitutable with them: it folds before case-folding and does not collapse whitespace, so the same input yields a different form. The pair is closable and the trio is not; closing it means a shared primitive in the core text-folding module and rewiring a shipped, heavily gated country matcher, which is wider than this ruled row and is left reported rather than taken.

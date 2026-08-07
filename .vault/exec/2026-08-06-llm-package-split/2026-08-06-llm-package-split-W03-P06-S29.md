---
tags:
  - '#exec'
  - '#llm-package-split'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:5cd2bd35ce8b737064dcb6d6e1eb2fc6bebb165dbc74a8be0950a4b030b1e434'
step_id: 'S29'
related:
  - "[[2026-08-06-llm-package-split-plan]]"
---

# Prove provenance survives persistence with a strict save-load-equality roundtrip against the real encrypted namespace with every defaultable field populated non-default, paired with an anti-tautology proof that deleting a persisted field reddens the load

## Scope

- `src/cadrumo/application/ledger/tests/`

## Description

- Add a draft fixture populating all three provenance axes off their defaults, across three different grounding outcomes.
- Roundtrip it through the real encrypted extraction-draft store and assert strict equality.
- Assert the nested ambiguity candidates survive, not merely the envelope count.
- Add an anti-tautology proof that deleting a required provenance field reddens the load.

## Outcome

The store already had a real-encrypted roundtrip and an anti-tautology proof, but every existing fixture left `provenance` at its empty default. Nothing asserted the store persisted it at all, so the coverage looked complete while the field it most needed to cover was untouched.

Provenance is the part a reader cannot reconstruct. A value that survives persistence while its origin and grounding do not looks identical to a value that was read exactly -- an ambiguous or contradicted reading silently becomes a confident one, and the operator loses the reason to check it.

The fixture deliberately uses three DIFFERENT outcomes rather than three of one: reconciled and anchored, ambiguous carrying competing candidates, contradicted carrying the note that explains what disagreed. Three envelopes of a single shape cannot distinguish a boundary that persists one envelope shape from one that persists all of them.

The ambiguous envelope is asserted in detail on purpose. Its candidates nest a level deeper than any other provenance field, so a boundary that flattens nested records loses exactly that and nothing else -- and would pass a test that only counted envelopes.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_extraction_draft_store.py -m "unit or integration" -n 0
    7 passed in 1.76s

Mutation-checked rather than assumed. Giving `grounding` a default so a dropped
field silently re-defaults:

    Failed: DID NOT RAISE ValidationError
    1 failed, 1 passed, 5 deselected in 1.10s

Mutation restored and the file verified back to zero markers.

## Notes

The anti-tautology proof was WRONG in its first form, and the way it was wrong is worth recording because it would have shipped as a false positive.

It validated a Python dict, and the expected regex did not match. The models are strict, so the dict path refuses the JSON-dumped `Decimal` as a string long before it reaches the deleted field: the refusal fired, but for an unrelated reason. Matching loosely -- or matching on `ValidationError` alone -- would have produced a green test that proved nothing whatsoever about provenance.

It now re-validates as JSON TEXT, which is the only path that reaches the field the test names. This is the second time in this campaign that strict-mode dict validation has silently changed what a test was measuring; the earlier instance was a CLI list payload asserting typed rows.

The mutation check is what converts the proof from plausible to demonstrated. Without it the test asserts that a refusal happens, not that the refusal is caused by the missing field.

---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:c5ca2a2abec7a188344aff67f92c1fec43149ddb2bb13794ccce99ccb4e4750b'
step_id: 'S90'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# The reverse-charge classification pair, read off real documents

## Scope

- `src/cadrumo`

## Description

- Generate two synthetic Spanish invoices differing in one printed line: the art. 84.Uno.2 reverse-charge mention alone, and the same mention beside a 21 per cent repercutido line, each with a provenance sidecar declaring synthetic origin, its content address and its size.
- Read both end to end through a real loopback endpoint speaking the runtime wire shape, with no model loaded and the reply authored by the test, so the mention arrives through the transcription rather than being handed to the check.
- Assert the lawful presentation derives the reverse-charge category and raises no finding, and that a zero rate beside a zero cuota is not read as tax charged.
- Assert the contradiction raises the blocking finding on its outcome and its field, never on a category, because the axis withholds the category exactly there and its only consumer reads the outcome.
- Assert the reverse charge's exclusion from the establishment-premise relief set, together with the exact membership of that set, since the exclusion assertion alone would pass against an empty one.
- Assert the two retencion slots reach the draft as grounded figures carrying provenance entries.
- Anchor the pair on its own premise: both documents still print the phrase the legend table matches, and that phrase still derives.

## Outcome

The pair reads real printed evidence rather than authored drafts. That distinction is the point of the row: a hand-built draft would exercise the finding while proving nothing about whether a document reaches it, which is the shape that ships a guard correct in logic and unreachable in wiring.

Two things were learned by measurement rather than assumed. The legend matcher case-folds but deliberately does not fold diacritics, so the fixtures had to print the accented mention as a correct transcription of a real invoice would; and the draft carries provenance as a list of per-field entries rather than a single origin, so the retencion regression asserts the entries for the two slots specifically.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_reverse_charge_reading_against_a_loopback_reader.py -n0 -q
    5 passed in 7.09s

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_evidence_corpus_parsing.py -n0 -q
    26 passed in 4.64s

    uv run --no-sync pytest src/cadrumo/application/ledger/tests -n0 -q -m unit
    1 failed, 1212 passed, 26 deselected

Each fixture was checked against the question of whether it would fail if the classification were wrong against the regulation, by mutating the predicate from outside the repository:

    [MUT zero reads as charged] predicate called 1x -> lawful doc yields a FINDING (fixture 1 REDS)
    [MUT charged reads as zero] predicate called 1x -> contradictory doc yields NO finding (fixture 2 REDS)
    [MUT relief set widened   ] membership now True -> doctrinal fixture REDS
    [CONTROL real predicate   ] lawful->None, contradictory->finding -> PASSED

## Notes

The single failure in the lane is a peer's identity-role test. Attributed by moving both new fixture documents out of the corpus, re-running to the identical failure, and restoring them; it does not read the corpus at all.

The legend matcher requiring the accent is a documented deliberate narrowing rather than a defect, but a transcription that drops diacritics derives absent and no contradiction can fire. That is worth a look on its own terms and is not changed here.

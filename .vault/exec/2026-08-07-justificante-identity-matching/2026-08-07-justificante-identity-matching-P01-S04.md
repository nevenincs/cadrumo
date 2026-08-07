---
tags:
  - '#exec'
  - '#justificante-identity-matching'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:b5b53f53656293c66c7a4be593c516d48dec0df97785daad89501f7ab22cf384'
step_id: 'S04'
related:
  - "[[2026-08-07-justificante-identity-matching-plan]]"
---

# Remove the presentation_id parameter entirely from matches_filing_target and its three now-dead pass-through wrapper parameters

## Scope

- `src/cadrumo/domain/justificante/_schema.py`
- `src/cadrumo/application/live/_justificante.py`
- `and src/cadrumo/application/live/_filed_observation_persistence.py`

## Description

With every site performing its own CSV check, no caller anywhere had a valid way
to populate `presentation_id`. A grep confirmed the only two remaining
`matches_filing_target` callers passing it were the two tests S05 covers; every
other `presentation_id=` occurrence constructs the model field, which stays.

## Outcome

Removed the parameter from `Justificante.matches_filing_target` and from all
three pass-through wrappers (`_justificante_matches_filed_observation`,
`_justificante_matches_capture_axis`, `_justificante_matches_filing_record`). The
`Justificante.presentation_id` FIELD is untouched - the receipt's own identifier
is still parsed and persisted; it is simply not a matching axis.

The docstring now states that verifying the receipt is the caller's own CSV
comparison and explains why no parameter for that axis exists, so the absence
reads as a decision rather than an oversight.

## Verification

`ty check` reports the removal at any call site passing the argument. Landed
together with S05's test updates in one tree state, because a landing that removed
the parameter while tests still passed it would leave HEAD failing to collect.

## Notes

This converts the recurrence risk from a docstring warning into a `TypeError`.
Gate proven to bite: an out-of-repo plugin restored a tolerant signature under
`-n0`, and the removal test went red.

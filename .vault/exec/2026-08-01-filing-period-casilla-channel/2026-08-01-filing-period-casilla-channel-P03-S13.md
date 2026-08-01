---
tags:
  - '#exec'
  - '#filing-period-casilla-channel'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:9e42eaf2f408eb38a5238e33311fab160720fe70ce0b89ac23e2968f5ab266fa'
step_id: 'S13'
related:
  - "[[2026-08-01-filing-period-casilla-channel-plan]]"
---

# Refresh the cli-sequence goldens moving decl.periodo values 1 through 4 to 1T through 4T across the 54 occurrences

## Scope

- `docs/_sequences`

## Description

- Back up all five hundred committed goldens before touching anything.
- Write a structural minimality checker that accepts only the intended change and refuses everything else.
- Mutation-test that checker against planted defects before trusting any verdict it gives.
- Refresh the seven affected pages through the owning verb, page by page, against an isolated storage root.
- Compare the backup against the refreshed tree and require a clean verdict before staging.

## Outcome

Nineteen goldens changed, and the whole delta came back with zero violations against the checker.

The refresh is not the single value move the plan anticipated. Re-executing produced four coupled classes: the token arriving on the string channel, thirty sites; the same casilla becoming a Decimal zero in the flat value mapping, thirty sites; the same zeroing seen through its observation, thirty sites; and content-addressed identifier churn, twenty-one distinct pairs across a hundred and forty-four sites, because the persisted revision content changed. Identifier churn was not accepted as "hashes may move": the old-to-new mapping had to be consistent across the whole tree in both directions, and each changed string had to be reproduced exactly by applying that mapping.

The checker was proven before it was trusted. Six planted defects were each localised to a path: a removed file, an added key, a changed exit code, a period value moved to a wrong token, a rendered text block altered beyond the accepted move, and a short identifier abbreviating no known pair. Identical trees report clean.

Two of the checker's own rules were wrong on first writing and were corrected against measurement rather than left to pass. The rendered casilla table prints the Decimal channel, so the period row moves to zero, not to the token as first assumed; and the short identifier form is a twelve-character tail that the full-length pattern never matched.

## Notes

The stated occurrence count is a grep artefact, not a count of token moves. Fifty-four was the number of raw matches for one period value spelling in the committed goldens. The real shape is thirty token moves, thirty zeroings in the flat mapping and thirty in the observations. Anyone re-deriving this from the count alone will look for the wrong thing.

Mutation testing found a defect in the checker itself. A clearing step that reset findings between its identifier pre-pass and its comparison pass would have discarded file additions and removals entirely, so a golden appearing or vanishing would have passed silently. It was caught because the file-removal mutation was re-run after the checker was widened, rather than assumed still covered.

Nineteen files changed but eighteen were committed. The nineteenth differed only in line endings and is byte-identical once normalised, so it was correctly excluded rather than forced in.

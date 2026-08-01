---
tags:
  - '#exec'
  - '#filing-period-casilla-channel'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:9e29907ada4579637a64961087f8e6ce03b8bff365884411007d901af884b988'
step_id: 'S04'
related:
  - "[[2026-08-01-filing-period-casilla-channel-plan]]"
---

# Verify the replay merge precedence already favours the string channel for the filing-period token (no code change was required)

## Scope

- `src/cadrumo/application/modelo/_revision_replay_inputs.py`

## Description

- Read the filing replay composition order and establish which mapping supplies the period casilla to the draft.
- Make no code change, the intent already holding at HEAD.
- Confirm by executed gate rather than by inspection alone.

## Outcome

This Step's intent is satisfied at HEAD with no diff, and none was manufactured to match the action text.

The filing replay builder composes the informational replay inputs, which are read from the persisted Decimal mapping, BEFORE the stored casilla inputs, which are read from the persisted string mapping. The later mapping wins on merge, so the token is already what reaches the draft. For a freshly calculated revision the informational branch does not even contribute the casilla: the engine's structural zero occupies the Decimal slot and the token occupies the string slot.

Confirmed by an executed gate, not by reading the merge order. The persisted-revision Modelo 303 end-to-end test calculates, persists, replays, builds the draft and exports a fixed-width fichero. It was one of the twenty-two baseline failures and now passes. Had replay supplied the structural zero or a bare ordinal, the typed text channel would have refused at draft build and that gate would still be red.

The stale-revision behaviour the governing decision describes is preserved unchanged: a revision persisted before this phase carries the ordinal in the Decimal mapping and no token in the string mapping, so replay stringifies it, the typed channel refuses, and the remedy is recalculation rather than coercion.

## Notes

The Step row read differently at dispatch. It said "replay the filing-period token from the string mapping instead of stringifying it out of the Decimal mapping", which implies an edit was expected. No edit was needed and none was made; that finding was reported, and the amending ruling folded it into the plan, so the row now reads as a verification with the no-change outcome stated in the row itself. This record is checked against that amended row, and the amendment is where the correction is owned.

A later phase auditing this commit against the plan should not look for a replay diff. There is none, by design.

---
tags:
  - '#exec'
  - '#profile-derived-selectors'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:c92684d3407bb940dc85bb255426d77823b39033ec8461b990112225e6780c40'
step_id: 'S07'
related:
  - "[[2026-08-04-profile-derived-selectors-plan]]"
---

# Filter derived paths out of the profile overview projection in the same commit as the refusal, closing the window where a row would render that the write door refuses

## Scope

- `src/cadrumo/application/user_profile/_overview.py`

## Description

## Outcome

The overview projection stops rendering derived paths, in the same commit as the refusal.

This is not a presentation-layer hide, which the ADR rejected outright. The refusal lands
with it, and the filter exists to close a window in which a row would still render while the
write door refused it -- the at-the-box check pronouncing admissible what the record then
rejects, which is the two-surfaces-disagreeing failure the refusal exists to prevent,
reintroduced at the point of entry.

Measured at the time it landed: the renta_family section fell from twenty-seven rows to
seven for an empty profile, exactly the twenty derived declarations, with no derived path
leaking through and both kept operator fields still rendered.

A later measurement corrected the campaign's own framing about which commit delivered that.
The deletion Step was briefed as the one that would drop the visible row count, and its
executor probed both schema states and reported the contradiction rather than massaging it:
declared field paths fell from one hundred and seventy-seven to one hundred and fifty-seven,
but the rendered row count did not move at all. The reason is here -- this filter matches by
PATTERN, independent of whether a per-year field declaration also exists, so the rows had
already gone when this commit landed. The deletion removes the declarations permanently and
shrinks the locale and registry surface, which is necessary and correct, but it is not what
moved the rows.

Both were needed and for different reasons: the filter for the transitional window, the
deletion for the permanent state. The coordinator's brief asserted otherwise and was wrong;
the correction came from an executor measuring rather than accepting the framing it was
given.

## Notes

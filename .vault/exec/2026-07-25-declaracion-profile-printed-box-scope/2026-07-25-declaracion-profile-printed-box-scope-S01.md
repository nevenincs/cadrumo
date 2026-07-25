---
tags:
  - '#exec'
  - '#declaracion-profile-printed-box-scope'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S01'
related:
  - "[[2026-07-25-declaracion-profile-printed-box-scope-plan]]"
---

# Drop the six non-printed-box targets from the extraction profile target list, retaining the printed-box targets it already carries, across both revisions per the operator ruling

## Scope

- `extraction profiles`
- `2 TOML files`

## Description

- Drop the six primitive targets from the `2023-y-siguientes` extraction profile, leaving 12 printed-box targets.
- Drop the five primitive targets present in `2009-y-siguientes`, leaving 4 printed-box targets.
- Replace the removed target block in both profiles with a comment recording why the primitives are absent.
- Narrow both profiles' `legal_refs` to the union of the retained targets' own refs.

## Outcome

Both revisions were re-scoped in one change, per the operator ruling recorded in the ADR. Loading each revision through the authority and inspecting the compiled schema confirms the post-drop target counts: 12 for 2023, 4 for 2009.

The 2009 profile carried five ids rather than six. `iva.autoconsumo.promotor.base` was never among its targets, and the underlying casilla does not exist in that revision at all, so there was no sixth to remove.

`legal_refs` had to move with the targets. Dropping the primitives drops LIVA art. 84 from both profiles, and art. 9 and art. 79 from the 2023 profile: the profile no longer claims to read a reverse-charge cuota or an autoconsumo base off the page.

## Notes

The removal was found already applied in the working tree by an interrupted prior session, cold for roughly eleven hours. It was adopted and completed rather than re-implemented or overwritten, per the live-WIP discipline.

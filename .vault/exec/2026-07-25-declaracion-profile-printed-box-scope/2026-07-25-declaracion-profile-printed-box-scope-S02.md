---
tags:
  - '#exec'
  - '#declaracion-profile-printed-box-scope'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:dc81e729873057fc130dd5195c15c092799a6c504d4d8cf2a3fe8cde6a1ab677'
step_id: 'S02'
related:
  - "[[2026-07-25-declaracion-profile-printed-box-scope-plan]]"
---

# Restate min_coverage at the level the form genuinely yields across all four annex quarters, accommodating legitimately blank optional boxes rather than assuming the 1T shape

## Scope

- `extraction profiles`

## Description

- Restate `min_coverage` on the 2023 profile from `"1"` to `"0.8333"`.
- Restate `min_coverage` on the 2009 profile from `"1"` to `"0.75"`.
- Record at each site how the figure was arrived at, and that the synthetic corpus cannot validate it.

## Outcome

The 2023 floor is measured, not chosen. Running the production extraction path over the four bundled AEAT published-facsimile annex quarters against the 12 retained targets gives 12/12, 11/12, 11/12 and 10/12, so coverage is 1.0000, 0.9167, 0.9167 and 0.8333. All four are now accepted where all four were previously refused. 10/12 is the highest floor every quarter satisfies; anything above it re-arms the refusal on 4T.

The 2009 floor is inferred and says so at the site. The repository bundles no printed render inside that revision's 2009-2022 window, so the figure cannot be measured the way the 2023 figure was. It admits one blank of four targets, matching the optional-blank class observed in the annex.

Both shortfall boxes are legitimately blank optional boxes, not pattern defects, so the floor had to admit them rather than assume the fully-populated 1T shape.

## Notes

Measured headroom at the worst quarter is exactly zero, which is inherent in taking the highest floor all four quarters satisfy. It is recorded as a finding in the companion layout-blind-corpus audit so a future refusal is diagnosed correctly rather than read as a parser fault.

All 15 synthetic fixtures score exactly 1.0 against the post-change profiles, confirming by measurement that the generated corpus is structurally incapable of validating this number.

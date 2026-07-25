---
tags:
  - '#exec'
  - '#declaracion-profile-printed-box-scope'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S05'
related:
  - "[[2026-07-25-declaracion-profile-printed-box-scope-plan]]"
---

# Update the 15 synthetic corpus fixtures and 48 expected-value entries across 8 fixture blocks that carry the moved expectations

## Scope

- `test fixtures`
- `corpus`

## Description

- Regenerate the 15 synthetic corpus PDFs and sidecars without the primitive line items.
- Verify the 48 current-template and 28 historical expected-value entries against the change.

## Outcome

The 15 fixtures are regenerated. The expected-value entries needed no edit at all, and that absence is the finding this feature was told not to swallow: all 76 entries, 48 current plus 28 historical, contain zero references to any of the six dropped ids, so every one survives the layout change untouched.

The plan's figure of 48 across 8 blocks is correct for the current-template module but scope-limited; the historical support module carries a further 28. Both were checked.

## Notes

Recorded in full in the companion layout-blind-corpus audit. The entries are not wrong; they establish that the value-level corpus measures totals and closures rather than layout.

---
tags:
  - '#research'
  - '#registry-m100-row-width-deferrals'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - "[[2026-06-04-registry-row-width-pressure-audit]]"
  - "[[2026-06-04-registry-row-width-pressure-plan]]"
---

# `registry-m100-row-width-deferrals` research: `Registry M100 row-width deferrals research`

## Scope

This retrospective research record grounds the M100-specific row-width
deferral slice that followed the registry row-width pressure pass. The
pressure pass lowered the general registry TOML reviewability baseline but
left five M100 rows near the remaining limit because those rows needed
separate legal-reference and equality-preservation review.

## Findings

- **R01:** The deferral scope is narrower than the parent row-width
  pressure plan. It is limited to formatting and table-shape work for the
  M100 rows that stayed above the preferred width after the baseline was
  reduced.
- **R02:** The plan must not alter legal references, source references,
  schema semantics, loader semantics, or unrelated dirty M100 fragments.
- **R03:** The active verification surface is the registry reviewability
  gate plus loader and committed-registry checks. Equality preservation is
  required for the 2020 nested-table conversion.

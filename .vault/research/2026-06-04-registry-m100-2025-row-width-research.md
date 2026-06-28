---
tags:
  - '#research'
  - '#registry-m100-2025-row-width'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-registry-m100-row-width-deferrals-plan]]'
  - '[[2026-06-04-registry-m100-row-width-deferrals-adr]]'
---

# `registry-m100-2025-row-width` research: `Registry M100 2025 row-width research`

## Scope

This retrospective research record grounds the follow-on M100 2025 row-width
slice after the M100 deferral plan lowered the registry TOML row-width
baseline. The remaining 2025 rows were clean formatting candidates above the
preferred 520-character headroom target.

## Findings

- **R01:** The prior M100 deferral slice left four M100 2025 `legal_refs`
  rows at 526 to 528 characters, below the 530 baseline but above the
  preferred headroom target.
- **R02:** The work is formatting-only: legal references, source references,
  schema behavior, loader behavior, and unrelated dirty fragments are out of
  scope.
- **R03:** Completion requires reviewability, committed-registry, loader, and
  plan gates.

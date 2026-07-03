---
tags:
  - '#exec'
  - '#cli-persona-testimonials'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S17'
related:
  - "[[2026-06-30-cli-persona-testimonials-plan]]"
---

# Replay raw Ana and Taller transcript roots through the current CLI

## Scope

- `tmp/personas`

## Description

- Inspected the Ana and Taller transcript closeout sections before replay.
- Replayed Ana's M303 arithmetic/export risk and Taller Norte's
  first-period/prior-filing risk against current behavior.
- Separated evidence artifact incompleteness from current product defects.

## Outcome

No current product defect reproduced. Ana's calculation values still match the
raw transcript arithmetic, and verification blocks on missing linked VAT
evidence rather than a missing export verb. Taller Norte's original profile was
an established 2020 activity filing 2025 1T, so current behavior correctly
fails closed through IVA-wallet authority guidance; a paired true first-period
profile calculates with prior compensation zero.

## Notes

Verification evidence included the required RAG search, 3 focused wallet and
first-period tests, 2 M303 export-reach tests, CLI export help showing the
local-only export surface, and direct temp CLI replays for Ana, established
Taller, and true-first-period Taller.

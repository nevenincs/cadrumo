---
tags:
  - '#exec'
  - '#modelo-115-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-115-calc-verify-plan]]"
  - "[[2026-04-27-modelo-115-calc-verify-adr]]"
  - "[[2026-04-27-modelo-115-rule-delta-reference]]"
---

# Step record — coverage docs flip

Plan reference:
`2026-04-27-modelo-115-calc-verify-plan` §4.1.

## Files changed

- `docs/coverage/modelos.md` — flipped the M115 row from the
  partial-Tier-L state to:
  - Formula ruleset column → `✅ (2024 + 2025 + 2026, calc-verify
    Tier-L #319)`
  - Tests column → `✅`
  - `declaración` import column → `✅ (2024 + 2025 + 2026,
    6-casilla full liquidación block #319)`
  - other columns preserve their pre-#319 state.
  Provenance line at the bottom updated to lead with #319 and
  preserve the #321 entry as the previous refresh.

## Verification

- `git diff docs/coverage/modelos.md` shows the row + provenance
  edits, no other lines touched.

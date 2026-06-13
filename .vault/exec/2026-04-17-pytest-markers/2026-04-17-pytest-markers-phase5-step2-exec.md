---
tags:
  - "#exec"
  - "#pytest-markers"
date: 2026-04-17
modified: '2026-04-17'
related:
  - "[[2026-04-17-pytest-markers-plan]]"
  - "[[2026-04-17-pytest-markers-adr]]"
---

# pytest-markers phase-5 step-2

## create-tests-readme

Authored `tests/README.md` as the canonical operator reference:

- Overview referencing charter #116 and the ADR.
- Marker tables for Axis A (unit / live_read / live_write) and Axis B (six domains) with selection command examples.
- Module-level mandate with a canonical header example.
- `live_write` ban: drop-not-skip, three factors, the exact phrase `I ACCEPT THE RISK OF FILING A LIVE TAX RETURN` verbatim, and a stern warning that the bypass does NOT enable a live submission (charter R3/R5 still apply).
- Bypass incantation: bash + pwsh one-liners, immediately followed by a "DO NOT RUN unless you are about to file a legally binding tax return" banner.
- Cross-references to `scripts/README.md` and `CLAUDE.md`.

Files touched: `tests/README.md` (new).

## verification

- `grep -c "I ACCEPT THE RISK OF FILING A LIVE TAX RETURN" tests/README.md` -> 3 matches (table row + bypass section + two one-liners = 3-4).
- `grep -n "live_write" tests/README.md` -> multiple matches.

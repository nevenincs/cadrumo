---
tags:
  - "#exec"
  - "#casilla-db"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-casilla-db-plan]]"
---

# casilla-db phase1 step2

Added canonical casilla settings and enforced verification on canonical writes.

- Modified: `src/aeat/config.py`
- Modified: `env/.env.example`
- Modified: `src/aeat/domain/casillas/catalogue.py`

## Description

Added `AEAT_CASILLAS_ROOT` and `AEAT_CASILLAS_REVIEW_REQUIRED`, resolved the
default corpus root to `corpus/casillas`, and updated `save_casillas` so it
refuses to persist invalid canonical data.

## Tests

`tests/test_config.py` stayed green, and the catalogue unit tests cover
malformed records, cross-reference failures, optional-field round-trips, and
review-required enforcement.

---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S22'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
---

# `declaracion-extraction-architecture` `W03.P07.S22`

ALREADY SATISFIED — M130 `03 = 01 − 02` cross-check is already present in the registry as formula `modelo-130-rendimiento-neto` and casilla `03` is already in `verification_expectations.computed_casillas`.

## Description

Verified against `src/aeat/_data/registry/aeat/modelos/130.toml` revision `2019-y-siguientes`:

- Formula `modelo-130-rendimiento-neto` exists with `target = "03"` and `expression = { op = "subtract", args = [{ casilla = "01" }, { casilla = "02" }] }`.
- `verification_expectations` stanza `modelo-130-calculation-verification` lists `computed_casillas = ["03", "04", "07", "09", "11", "12", "13", "14", "17", "19"]` — casilla `03` is included.
- The construct `modelo-130-direct-estimation-instalment` lists `formulas = ["modelo-130-rendimiento-neto", ...]` and `verification_expectations = ["modelo-130-calculation-verification"]`.

The `03 = 01 − 02` intra-filing cross-check is fully wired. No restoration was needed. The verification gate would fire on any filing where the extracted `03` diverges from `01 − 02` by more than the 0.01 tolerance.

Step is closed as already-done.

## Tests

- `test_committed_registry.py`: 41/41 passed — M130 snapshot validates including verification stanza
- No files modified

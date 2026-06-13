---
tags:
  - '#exec'
  - '#no-synthetic-sede-live-surfaces'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S07'
related:
  - '[[2026-05-26-no-synthetic-sede-live-surfaces-plan]]'
---

# `no-synthetic-sede-live-surfaces` `P03.S07`

Ran the focused registry and Sede validation gates for the no-synthetic policy.

- Modified: `.vault/plan/2026-05-26-no-synthetic-sede-live-surfaces-plan.md`

## Description

The validation focused on the schema/guard invariant, Modelo 100 and Modelo 349
registry surfaces, oracle resolution/applicability/parity behavior, committed
registry loading, and the directly related offline Sede GROI, NIF-IVA, and Renta
WEB Open driver tests. No live Sede call was made and no synthetic data was sent
to any AEAT-hosted surface.

The broader Sede declarations batch still has three unrelated Modelo 303
export-layout failures around `modelo-303-envelope-marker`; that is concurrent
303 work and remains outside this ADR slice.

## Tests

Passed:

- 133-test focused registry gate covering remote guard, authenticated simulator,
  Modelo 100, and Modelo 349.
- 115-test registry oracle/applicability/parity gate.
- 41-test committed registry loader gate.
- 20-test offline GROI Sede driver gate.
- 31 selected tests across NIF-IVA and Renta WEB Open offline Sede driver gates.
- Ruff passed for changed registry and Sede Python files.

Known out-of-scope failure:

- `test_declarations.py` broader Sede batch: three Modelo 303 export-layout
  failures on `modelo-303-envelope-marker`.

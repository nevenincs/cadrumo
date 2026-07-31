---
tags:
  - '#exec'
  - '#m210-irnr-phase-2-engine'
date: '2026-07-10'
modified: '2026-07-10'
body_hash: 'sha256:f61f752415a250cc3166a77b1f175b3105df98d9a745cff26d962decf6e76879'
step_id: 'S06'
related:
  - "[[2026-05-27-m210-irnr-phase-2-engine-plan]]"
  - "[[2026-07-10-m210-irnr-phase-2-engine-adr]]"
---

# Author the strict Modelo 210 annual grouped-renta contract grounded in the bundled Article 2 text

## Scope

- `src/aeat/domain/modelos/_row_models.py`
- `src/aeat/application/modelo/_m210_agrupacion_renta.py`
- `src/aeat/_data/registry/aeat/modelos/210`

## Description

- Add a persisted `Modelo210AgrupacionRentaRow` for annual 0A work.
- Enforce lease/sublease code eligibility, a shared raw official code, rate, property/right, payer identity, non-negative values, and the code-35 multiple-payer exception.
- Ground the 0A registry gate in the official Article 2 source and reject manual annual rows when the ledger source owns them.

## Outcome

The persisted row contract supplies the formerly absent data shape without fabricating a predicate DSL. It is limited to the official annual rental grouping rules and is covered by domain and end-to-end behavioral tests. Landed in `8f5f690ed0`.

## Notes

The original predicate-only approach is superseded by the approved row-model design; no ungrounded general grouping facility was added.

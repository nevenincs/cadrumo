---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S43'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# provision the Modelo 303 casilla 44 prorrata_regularizacion binding rows for current registry revisions, convert the target from manual to bound only with legal/source citations and formula-consumption implications proven

## Scope

- `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/`
- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/`
- `src/aeat/domain/calculations/registry/tests/`

## Description

- Ran the three mandated `vaultspec-rag` searches for Modelo 303 casilla 44 binding, manual-to-bound consumption, and current S43 registry revision context.
- Read the cross-period-prorrata plan and ADR, the S42 exec record, the exec-step template, the Modelo 303 registry revision files, and the current binding/formula runtime surfaces before editing.
- Provisioned `modelo-303-prorrata-regularizacion-casilla-44` binding rows for the 2009 and 2023 Modelo 303 registry revision families with `prorrata_regularizacion` selectors, LIVA arts. 104-105 grounding, AEAT/BOE source references, and source citations.
- Exposed the new binding rows through the Modelo 303 construct envelopes while leaving casilla 44 as `input_kind = "manual"` in both revision families.
- Updated focused registry tests to prove the real binding row shape, selector contract, legal/source grounding, scalar aggregation default, construct exposure, and the current formula non-consumption state.
- Updated the prorrata silent-zero advisory comment so it describes the provisioned binding row without claiming live resolver consumption.

## Outcome

- The `prorrata_regularizacion` binding source is now declared by the current committed Modelo 303 2009 and 2023 registry revision families.
- Casilla 44 remains manual because the current engine has no live `prorrata_regularizacion` resolver yet and current Modelo 303 formulas do not consume casilla 44 into `iva.cuota-deducible-total` or the 2023 DR303 casilla 45 projection.
- Bound conversion is intentionally blocked for S43: forcing `input_kind = "bound"` now would require callers to pass a synthetic zero binding value or risk an ungrounded default before the S45/S46 calculation-order and resolver work lands.
- `uv run --no-sync ruff check` over the touched registry tests passed.
- `uv run --no-sync pytest -q` over touched registry tests plus binding build/selector tests passed with 95 tests.
- `uv run --no-sync vaultspec-core vault check frontmatter --feature cross-period-prorrata` passed.
- `uv run --no-sync vaultspec-core vault check features --feature cross-period-prorrata` passed.
- `uv run --no-sync vaultspec-core vault plan check cross-period-prorrata` passed.

## Notes

- S43 did not edit resolver, enrollment, application mesh, Modelo 390, or deferred application source lists.
- S43 did not widen the selector to annual `0A`; the current committed Modelo 303 registry period surfaces remain quarterly/monthly rather than annual.
- The application resolver disposition remains deferred for later steps; this record closes S43 as a provisioned registry binding with an honest manual-target blocker, not as live calculation consumption.

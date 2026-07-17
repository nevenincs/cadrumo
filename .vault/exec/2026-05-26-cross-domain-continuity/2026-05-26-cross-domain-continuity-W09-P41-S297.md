---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-01'
modified: '2026-07-17'
step_id: 'S297'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R8-ROSA-CRITICAL M131 DPA-to-page1 calculation chain not executing under estimacion objetiva modulos regime

## Scope

- `bindings exist for personal asalariado modulo unidades modulo rendimiento neto but motor receives them and returns zeros`
- `formula casilla 04 equals casilla 01 times casilla 02 divided by 100 does not fire`
- `pago fraccionado por modulos cannot be computed`
- `src/aeat/_data/registry/aeat/modelos/131/`

## Description

- Ground S297 with RAG and a dedicated M131 DPA/page_1 reference note.
- Add an M131-only application calculation bridge that projects fixed-record datos-base bindings into liquidation casilla inputs `01` and `02`.
- Keep liquidation casilla `04` on the official no-datos-base branch driven by casilla `03`.
- Preserve explicit operator casilla-input precedence over projected backend values.
- Add real secure-storage application tests for page_1 projection, DPA rendimiento fallback into `01`, unrelated fixed-record binding isolation, and caller-precedence behavior.
- Run focused M131 registry, advisory, application projection, ruff, and reviewer gates.

## Outcome

- Closed the observed zero-result path for supplied M131 page_1 datos-base values: page activity `rendimiento-neto`, `porcentaje`, and `resultado` now feed casillas `01` and `02`, then existing formulas carry the result through `07`, `10`, `13`, and `15`.
- Added a grounded DPA partial bridge: precomputed DPA `modulo-*-rendimiento-neto` can supply casilla `01` when page_1 base values are absent.
- Preserved the official `04 = percent(03, objective_no_base_fractional_payment_rate)` calculation and guarded it in tests.
- Code review reported no S297 findings.
- Validation passed with `39` focused M131 tests, including the new `4` projection tests.

## Notes

Raw DPA module units are not converted into annual rendimiento through annual Orden modulos coefficient tables in this step. The current closure consumes precomputed DPA rendimiento and page_1 datos-base activity values only; a full coefficient-table oracle remains a separate hardening domain.

The worktree contained unrelated concurrent edits in `src/aeat/application/modelo/_calculation_actions.py` around the Modelo 303 IVA-compensation import path. Those hunks were left out of the S297 scope.

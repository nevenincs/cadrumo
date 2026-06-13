---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-05-27'
modified: '2026-05-27'
step_id: FU-182
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-sergio-cli-testimonial-audit]]"
---

# cross-domain-continuity FU-182 Step Record

## Task

CRITICAL — M123 retención does not flow to casilla 0597 (Sergio C3, task #182).

## Root Cause

Casillas 0596 and 0597 in the 2024 M100 revision lacked `input_kind = "bound"` and
`binding = ...` fields. `_resolve_bound_casilla_inputs_for_available_bindings` in
`_actions.py:1643` skips casillas where `casilla.input_kind != "bound"`, so both
bindings were accepted without error but their values never reached the engine.

The same gap affects M111 → 0596 (also fixed here as it shares the identical
structural pattern and fixing only M123 would leave M111 silently broken).

## Changes

- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/casillas/0578-0596.toml`
  Added `input_kind = "bound"` and `binding = "renta-2024-modelo-111-retenciones-periodicas"`.

- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/casillas/0579-0597.toml`
  Added `input_kind = "bound"` and `binding = "renta-2024-modelo-123-retenciones-periodicas"`.

- `src/aeat/domain/calculations/registry/test_modelo_100_retenciones_binding_wiring.py` (new)
  5 tests: M123→0597 wiring, M111→0596 wiring, 0597→0609 downstream flow,
  zero-value anti-tautology, proportional delta guard.

## Test Results

All 5 new tests pass. Settlement chain tests (6) unaffected. Pre-existing failures
in `test_modelo_100_ahorro_base_chain.py` and `test_modelo_100_tarifa_real.py` are
pre-existing (missing relation/date binding values in those fixtures, unrelated to
this change).

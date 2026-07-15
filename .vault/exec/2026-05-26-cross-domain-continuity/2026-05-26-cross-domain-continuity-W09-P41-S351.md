---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-11'
modified: '2026-07-15'
step_id: 'S351'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# FU-S279-A low priority typed LogExtra pydantic model to upgrade Mapping[str, object] annotations in service-layer logging helpers. DEFERRED-WITH-REASON: architect #141 ruled the current Mapping[str, object] correct with no defect, so this is a non-blocking future contract-tightening only

## Scope

- `service-layer helpers are correctly using Mapping[str`
- `object] today (per architect #141 verdict) but a typed LogExtra would tighten the contract`
- `future W09 improvement`
- `src/aeat/application/`

## Description

- The operator directed all open plan steps be closed for real; this step's prior
  deferred-with-reason disposition (architect ruling #141: the `Mapping[str, object]`
  annotation was correct, no defect) is superseded by that directive. Implemented the
  typed `LogExtra` tightening architect #141 identified as a legitimate future
  improvement rather than leaving it deferred indefinitely.
- Added `cadrumo.core.logging.LogExtra`, a frozen Pydantic v2 `RootModel[dict[str,
  LogExtraValue]]` where `LogExtraValue = str | int | float | bool | None` — the
  closed union of scalars every current `as_extra()` emitter actually writes into
  the stdlib `logging.Logger.debug(..., extra=...)` boundary. A future field carrying
  a nested mapping or other non-serialisable value now fails loudly at construction
  with a `pydantic.ValidationError` instead of surfacing later as a JSONL-sink
  serialisation surprise. Exposes `for_logging()` to materialise the plain `dict`
  stdlib `logging` requires (a `RootModel` is not iterable the way
  `logging.Logger.makeRecord` needs).
- Upgraded the two `Mapping[str, object]`-returning `as_extra()` helpers under
  `src/cadrumo/application/` in one atomic sweep with every caller:
  `PerModeloAggregationLogFields.as_extra` (`application/aggregation/_service.py`) and
  `OperatorSurfaceLogFields.as_extra` (`application/operator_surface/_models.py`), both
  now returning `LogExtra`. Updated their two production call sites
  (`application/aggregation/_service.py`, `application/operator_surface/_contract.py`)
  to call `.as_extra().for_logging()` at the `extra=` boundary, and their two test
  assertions (`application/aggregation/tests/test_per_modelo_service.py`,
  `application/operator_surface/tests/test_contract.py`) to compare against
  `.as_extra().for_logging()`.
- Left the domain-layer `CensoModeloFoundationLogFields.as_extra() -> dict[str,
  object]` (`domain/calculations/registry/_censo_modelos.py`) untouched: it already
  returns a concrete `dict`, not `Mapping[str, object]`, and sits outside this step's
  declared `src/cadrumo/application/` scope.
- Added real-behavior tests for the new model in `src/cadrumo/core/tests/test_logging.py`:
  a `for_logging()` materialisation check, an anti-tautology rejection test (a nested
  mapping value must raise `pydantic.ValidationError`), and a full stdlib-logging
  pipeline round-trip using a real `logging.Handler` subclass capturing the emitted
  `LogRecord` and asserting the typed fields survive unchanged.

## Outcome

- `ruff check` and `ruff format --check` clean on every touched file.
- Focused suites green: `pytest src/cadrumo/core/tests/test_logging.py
  src/cadrumo/application/aggregation/tests/test_per_modelo_service.py
  src/cadrumo/application/operator_surface/tests/` — 105 passed.
- `pytest --collect-only -q` clean for `src/cadrumo/core`, `src/cadrumo/application/aggregation`,
  `src/cadrumo/application/operator_surface` (1270/1278 collected, 8 deselected by marker).
- A full-tree `pytest --collect-only -q src/cadrumo` run reds on an unrelated, actively
  in-flight peer campaign (M131 2024 módulos-engine registry fragments under
  `src/cadrumo/_data/registry/aeat/modelos/131/revisions/2024/{casillas,formulas,parameters}/`,
  currently untracked working-tree WIP) causing `RegistryValidationError: unknown legal id
  'orden-hfp-1359-2023:...'` and cascading `overview`/`export` collection errors. None of
  those paths were touched by this step; confirmed via `git status --short` before and
  after this change (per `full-tree-gate-must-distinguish-owner`).
- `python -m dev.docs.apidocs scaffold --check` reports no stub drift.

## Notes

- This step is now genuinely closed with working code, not re-deferred: the typed
  `LogExtra` model exists, both application-layer service helpers consume it, every
  caller and test was swept in the same change, and the model is independently
  tested against the real stdlib logging pipeline.

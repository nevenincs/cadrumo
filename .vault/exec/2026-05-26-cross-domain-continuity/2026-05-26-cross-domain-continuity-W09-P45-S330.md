---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:22fab2f1610c657f9baaaba970741b471b90c1a5fc82102b5b7ed5da54992a4c'
step_id: 'S330'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R9-ZSOFIA-C state tokens borrador and verificado_completo leak Spanish in operator-facing context

## Scope

- `when emitted alongside operator prose route via tr() with locale-mapped human-readable label OR document they are technical identifiers and keep raw Spanish but always paired with translated prose`
- `src/aeat/entrypoints/cli/_modelo.py`

## Description

- Ground S330 through `vaultspec-rag search` and inspect the modelo renderer state emitters.
- Add locale-backed human state labels for modelo work-unit and calculation-revision text output.
- Preserve raw lifecycle tokens on JSON payload fields and machine identifiers.
- Add focused renderer-level unit coverage with real `WorkUnit` and `CalculationRevision` objects.
- Add English, Spanish, Catalan, and Hungarian state-label locale leaves through `aeat.locales set`.

## Outcome

- Text renderers now print operator-facing labels for draft, verified-complete, filed, superseded, and discarded states.
- `CalculationRevisionPayload.state` and `WorkUnitPayload.state` remain raw enum-token values for machine consumers.
- Focused pytest, ruff, and locale scaffold/audit checks passed.

## Notes

- Preserved the pre-existing docstring-only edits in `_modelo_rendering.py`.
- Code-review pass found one test helper should construct a verified revision through the real model constructor; fixed before closure.

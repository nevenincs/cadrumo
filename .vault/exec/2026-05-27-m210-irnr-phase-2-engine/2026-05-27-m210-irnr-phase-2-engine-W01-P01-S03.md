---
tags:
  - '#exec'
  - '#m210-irnr-phase-2-engine'
date: '2026-07-09'
modified: '2026-07-10'
body_hash: 'sha256:164a74e289d8320db959acb793df3229b08217842ba6184ab45285597a65b2a1'
step_id: 'S03'
related:
  - "[[2026-05-27-m210-irnr-phase-2-engine-plan]]"
---

# declare the official tipo-de-renta code as a typed Typer Choice at the M210 CLI boundary and add its locale keys across en/es/ca/hu through the locale CLI

## Scope

- `src/aeat/entrypoints/cli/_modelo.py`

## Description

- Surface the official tipo-de-renta code at the M210 CLI boundary. A static Typer `Choice` cannot render for one casilla's value inside the generic `work calculate --casilla key=value` surface, so build the sanctioned architecture-boundaries fallback: a registry-driven validation+refusal at the `_calculate_input.py` text-casilla boundary, keyed on the casilla `semantic_role = "irnr_tipo_renta"`.
- On an undeclared value, refuse with an instructive error that LISTS the accepted declared codes and names a fetch-gated code as fetch-gated (`08` → "not yet grounded, cannot be filed yet") rather than a bare "invalid"; a genuinely-unknown value additionally names the pending-grounding set. Add `FETCH_GATED_M210_TIPO_RENTA_CODES` to core to distinguish the two.
- On acceptance, PROJECT the operator-entered official code to its `TipoRentaIrnr` rate-concept token (the value the engine keys the rate table on) — the operator declares the code the form asks for while the rate machinery keeps its conceptual key.
- Author the two refusal messages as typed `translated_message` locale keys across en/es/ca/hu through the `python -m aeat.locales` CLI (English reproduces the operator-facing text; es/ca/hu genuinely translated).

## Outcome

An operator entering an M210 `tipo_renta` code gets an instructive, localised boundary: a declared code (e.g. `01`) is accepted and projected to its concept (`general`); a fetch-gated code (`08`) is refused as not-yet-grounded; an unknown code (`99`) is refused with the accepted and pending-grounding sets. Gate results: ruff + ty clean; locale `scaffold --check` + `audit` clean (parity + honesty); `test_calculate_input_error_localization` (incl. 3 new boundary tests: accept+project, fetch-gated refusal, unknown refusal) + the M210 calculate regression = 75 passed, zero regressions; `test_parity` + `test_locale_translation_honesty` + `test_self_referential_string_conformance` green.

## Notes

The boundary projects code→concept for the calc rate key, so codes that share a concept (arrendamiento `01` and empresariales `03` both `general`) collapse to that concept at input; per-code form-fidelity display belongs to the fetch-gated full-casilla schema (Slice C), not this axis. The S03 test is a boundary-level unit test on the validator the CLI invokes (matching the sibling `_text_value` localization test pattern), not a full CLI-flow integration test.

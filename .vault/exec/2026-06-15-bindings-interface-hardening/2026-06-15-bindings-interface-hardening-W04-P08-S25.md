---
tags:
  - '#exec'
  - '#bindings-interface-hardening'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S25'
related:
  - "[[2026-06-15-bindings-interface-hardening-plan]]"
---




# replace the --binding numeric-vs-enum try-Decimal-except heuristic with a registry-data-type-driven coercion that rejects a malformed amount instead of reclassifying it as an enum

## Scope

- `src/aeat/application/modelo/_calculate_input.py`
- `src/aeat/entrypoints/cli/_modelo_cli_support.py`

## Description

- Replace the `try Decimal/except` numeric-vs-enum heuristic in `build_work_calculate_input_bundle` with a registry-data-type-driven router.
- Add `_binding_input_channel`, which classifies each `--binding` override by the binding's declared engine channel: `enum_consumed_binding_ids(revision)` marks the enum channel; every other declared binding is the decimal channel. An unknown binding id refuses with the accepted set.
- Route enum-channel overrides verbatim into `enum_binding_values`; coerce decimal-channel overrides through `_decimal(..., flag="--binding", key=key)` so a malformed amount REFUSES instead of silently reclassifying as an enum string.
- Add `ModeloCalculateBindingInputError` with an error-code registry entry (`REFUSED_MODELO_CALCULATE_BINDING_INPUT`) and the `application.modelo.errors.calculate_binding_unknown` locale key across en/es/ca/hu.

Modified files: `src/aeat/application/modelo/_calculate_input.py`, `src/aeat/core/errors/registry/_application_part2.py`, `src/aeat/locales/{en,es,ca,hu}.yml`.

## Outcome

`--binding` classification is now by declared registry channel, not parse success. A real-CLI test proves `irpf.previous_year_economic_activity_net_income=12abc` (a decimal-channel M130 binding) refuses with a decimal-shape error naming the binding, flag, and value; a companion test proves the M200 enum binding `modelo-200-2024-profile-legal-entity-form=sl` is accepted, confirming the refusal is channel-specific. The unknown-binding refusal names the accepted set, satisfying no-silent-under-declaration and the CLI-Choice-hint mandate.

## Notes

The `_modelo_cli_support.py` override parser (`validate_binding_key`) was left unchanged — it validates key SHAPE only; the channel/type routing belongs in the application bundle builder where the revision is resolved. The malformed-numeric refusal surfaces at the CLI boundary as `REFUSED` category; its message carries the binding name and bad value. The en.yml locale leaf was committed by the peer quality-sweep bot before the es/ca/hu translations landed, so those three were re-applied and committed here.

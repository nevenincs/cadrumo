---
step_id: "S27"
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-28
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W01.P01.S27

**Status**: closed

## What was done

Introduced `WizardAnswerTypeError(CoreValidationError)` in `src/aeat/application/wizard/_errors.py` after `WizardCompileError`. Added `CoreValidationError` to the import from `...core.errors`.

Replaced 13 bare `raise TypeError(...)` coercion sites in `src/aeat/application/wizard/_setup_answers.py` with `raise WizardAnswerTypeError(...)`. The pydantic `@model_validator` `ValueError` raises (spouse field cross-field checks, EU/EEA country check) were deliberately left unchanged as they are pydantic invariant validators, not type-coercion boundaries.

Sites migrated (line numbers after edit):
- L186: `_parse_iva_regime` — iva_regime type guard
- L197: `_parse_entity_type` — entity_type type guard
- L208: `_parse_legal_entity_form` — legal_entity_form type guard
- L219-221: `_parse_irpf_estimation_regime` — irpf_estimation_regime type guard
- L230: `_parse_situacion_familiar` — situacion_familiar type guard
- L244-246: `_parse_unidad_familiar_descendientes_exclusivos` — bool/blank type guard
- L255: `_parse_irpf_special_regime` — irpf_special_regime type guard
- L266: `_parse_fiscal_residency` — fiscal_residency type guard
- L293: `_parse_taxation_type` — taxation_type type guard
- L304: `_parse_sex_code` — sex code type guard (taxpayer_sex + spouse_sex)
- L315-317: `_parse_marital_status` — marital_status type guard
- L348: `_parse_disability_grade` — disability grade type guard (taxpayer + spouse)
- L357: `_parse_tax_residence_ccaa` — CCAA type guard

Registered the new error under code `REFUSED_WIZARD_ANSWER_TYPE` (category `REFUSED`, message key `errors.refused.refused_wizard_answer_type`) in `src/aeat/core/errors/registry/_application.py`.

Added locale key `errors.refused.refused_wizard_answer_type` via `python -m aeat.locales set` to all 4 locale files (en, es, ca, hu). Locale audit shows no remaining drift on this key.

## Files touched

- `src/aeat/application/wizard/_errors.py` — added `WizardAnswerTypeError(CoreValidationError)`
- `src/aeat/application/wizard/_setup_answers.py` — imported `WizardAnswerTypeError`; replaced 13 `TypeError` raises
- `src/aeat/core/errors/registry/_application.py` — registry entry for `WizardAnswerTypeError`
- `src/aeat/locales/en.yml`, `es.yml`, `ca.yml`, `hu.yml` — locale key added

## Commit

`fb551c34f`

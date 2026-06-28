---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: S575
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W10.P41.S575`

Added `ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR` markers on 14 `@field_validator(mode='before')` def lines in `core/profile.py`.

- Modified: `src/aeat/core/profile.py`

## Description

Each `@field_validator(mode='before')` method that returns `-> Any` in `ProfileAnswers` now carries an inline rationale comment explaining that Pydantic's `mode='before'` contract requires the `Any` return annotation; the actual runtime return is always a typed StrEnum/enum member. Validators covered: `_parse_iva_regime`, `_parse_tax_residence_ccaa`, `_parse_entity_type`, `_parse_legal_entity_form`, `_parse_irpf_estimation_regime`, `_parse_situacion_familiar`, `_parse_unidad_familiar_descendientes_exclusivos`, `_parse_irpf_special_regime`, `_parse_fiscal_residency`, `_parse_taxation_type`, `_parse_sex_code`, `_parse_marital_status`, `_parse_disability_grade`, `_parse_new_entity_first_two_profit_periods`.

## Tests

W10 inventory test `test_w10_p41_rationale_inventory.py` asserts all 14 validators carry the marker. 27/27 passed.

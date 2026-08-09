---
tags:
  - '#exec'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:0d89095ca665ef57ba7541313892765e4ec56d3160319f36e62c2b018e92b767'
step_id: 'S06'
related:
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
---

# Update the blocking-gate context and the profile_readiness_missing locale template to render label and legal ref per missing field in all four catalogues via dev.locales

## Scope

- `src/cadrumo/application/modelo/_profile_readiness_gate.py`
- `src/cadrumo/locales/{en`
- `es`
- `ca`
- `hu}.yml`

## Description

The Step's action text as originally written called for a four-catalogue locale-template edit. What actually shipped is different and, on inspection, correct: the `application.modelo.errors.profile_readiness_missing` template's `%{missing}` placeholder was already generic prose interpolation, so no catalogue needed a change. Instead, `_profile_readiness_gate.py` gained `_format_missing_requirement()`, which renders `"{label} ({legal_refs joined})"` (or bare `label` when a row has no `legal_refs`), and both raise sites (`_require_profile_filing_ready` and the fuller `modelo_work_profile_preflight_report`-driven refusal) now join every missing requirement through it before it reaches `%{missing}`.

## Outcome

Delivered, but not as the row described. The P04.S11 honesty review flagged this (finding `locale-step-describes-an-edit-that-was-never-made`): the four catalogues are byte-identical to their pre-campaign text, verified by reading `en.yml:1048`, `es.yml`, `ca.yml`, `hu.yml` directly. This record and the plan row's corrected action text (edited same-session) are the fix for the mismatch - no further code change was needed, the row just described the wrong file.

## Verification

`pytest src/cadrumo/application/modelo/tests/test_profile_readiness_gate.py src/cadrumo/entrypoints/cli/tests/test_modelo_work_readiness_ux.py -m "unit or integration" -n 0` - all pass, including regressions asserting the blocking-gate message contains the catalogue label (`Activity description` / `Descripción de la actividad`, resolved via `profile_field_label` rather than hardcoded) and, for the M210 case, both `legal_refs` entries joined onto one row.

## Notes

The plan row's action text was corrected in the same session that wrote this record, to state what actually landed rather than what was originally planned. See `2026-08-09-profile-requirement-grounding-audit` finding `locale-step-describes-an-edit-that-was-never-made`.

---
tags:
  - '#exec'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:ba036f37af1c288bfb321cacf4b12444eda4ca57b7ac7f2318a5a4f5b7a39612'
step_id: 'S08'
related:
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
---

# Run the JSON-schema-conformance and locale-coverage-parity gates and fix any red findings

## Scope

- `src/cadrumo/entrypoints/cli/tests/`
- `src/cadrumo/tests/`

## Description

Ran the JSON-schema-conformance gate (`test_json_schema_conformance.py`), the documented-command-conformance gate, and the locale-coverage/parity/translation-honesty trio (`test_parity.py`, `test_locale_translation_honesty.py`, `test_locale_coverage_hardened_errors.py`, `test_locale_coverage_inventory.py`) against the enriched payloads and message. No locale catalogue edit was needed (see `P02.S06`).

## Outcome

Green on first run and on every re-run after subsequent P04 review fixes (the added `modelos` field on both payloads and the reworked label/grounding logic did not perturb these gates).

## Verification

`pytest src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py src/cadrumo/tests/test_parity.py src/cadrumo/tests/test_locale_translation_honesty.py -m "unit or integration"` - 726 passed, re-run after the P04.S10 review fixes with the same result.

## Notes

None.

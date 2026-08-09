---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:4a1a781ee407aed01ed7353c9bf878545ed30ee9bc4b09245613f0af678c3068'
step_id: 'S22'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Add real tests asserting the undeclared taxpayer-model refusal names the missing facts and reads as a refusal

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_overview_profile_refusal_grounding.py`

## Description

- Added an anchor test asserting both taxpayer-model fields have operator labels differing from their selector tokens.
- Added a test asserting an undeclared entity type is named by label, and that the raw token does not appear.
- Added a test asserting a natural person with a declared entity type but no income categories is told about the categories and NOT about the entity type.

## Outcome

Both branches of the conditional are covered, including the negative half of the second branch, which is the assertion that actually protects the operator from being sent back to a field they already filled in.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_overview_profile_refusal_grounding.py -m integration -n 0 -q
    10 passed in 17.54s

## Notes

The first draft failed on model construction because the taxpayer profile requires an IVA regime, and carried a near-tautological assertion (`assert expected_label or requirements`) that could not fail, plus an unused helper stub left over from an abandoned approach. All three were corrected: the assertion now compares the label against the rendered text, which is what it was supposed to check.

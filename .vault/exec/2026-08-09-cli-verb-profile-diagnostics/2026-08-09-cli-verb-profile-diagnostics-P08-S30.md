---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:60dccf8fecab2a4dc133c6954f380029e732ae9723c763505f634ae4ff44f3ca'
step_id: 'S30'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Name the required declarant-identity fields by their schema-derived labels in the export no-profile refusal instead of hard-coding two paths into the sentence

## Scope

- `src/cadrumo/application/modelo/_export.py`

## Description

- Passed a `requirements` context value to the no-persisted-profile export refusal, built by the same identity-rendering helper the sibling name-missing refusals already use.

## Outcome

The two refusals raised from this function now name their fields the same way. Previously the branch reached when a profile EXISTS but lacks a name rendered schema-derived labels, while the branch reached when NO profile exists spelled two dotted paths into its sentence - so the same two fields were named two different ways depending on which branch fired.

This is a cold-start refusal, and cold-start refusals were explicitly scoped OUT of this work. The distinction that puts it back in scope: it does not merely report that no profile exists, it instructs the operator to populate two named fields. Once a refusal names fields, the names must come from the schema, regardless of what triggered it.

The refusal CONDITION is unchanged.

## Verification

    uv run --no-sync pytest src/cadrumo/application/wizard src/cadrumo/application/modelo/tests/test_export_declarant_identity_grounding.py src/cadrumo/application/modelo/tests/test_export_headers.py src/cadrumo/application/tests/test_diagnostics.py -m "unit or integration" -n 0 -q
    376 passed in 31.82s

## Notes

No new helper was written; the existing one already rendered exactly this pair of fields for the adjacent branches.

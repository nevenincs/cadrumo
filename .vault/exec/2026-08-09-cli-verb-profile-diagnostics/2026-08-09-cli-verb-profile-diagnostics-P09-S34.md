---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:1bec7ea8c1e7e23957f476b0ce49280f076eafbbfe6d95f9597c2d53b04fae79'
step_id: 'S34'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Name the required profile identity field by its schema-derived label in the live-auth missing-tax-id refusal

## Scope

- `src/cadrumo/application/auth/_sessions.py`

## Description

- Passed the same grounded requirement on the Cl@ve missing-tax-id refusal's context and removed the dotted path from its sentence.

## Outcome

Both refusals raised from this module now name the same field the same way, from the same source.

They previously spelled the same path into two separately translated sentences, so the field was named twice in four catalogues with nothing keeping the eight strings consistent with each other or with the schema.

The refusal CONDITION and the fail-closed identity comparison below it are untouched. That comparison normalises both sides before comparing, and nothing here changes what it accepts or refuses.

## Verification

    uv run --no-sync pytest src/cadrumo/application/auth -m "unit or integration" -n 0 -q
    310 passed in 74.83s (0:01:14)

## Notes

The sibling operator-alignment messages were inspected and deliberately left alone: they describe the field in natural prose and pair it with a concrete CLI command, which is already actionable and names no internal identifier.

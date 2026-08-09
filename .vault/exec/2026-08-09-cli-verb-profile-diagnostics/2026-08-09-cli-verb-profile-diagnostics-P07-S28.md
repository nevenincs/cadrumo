---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:d9f44b98fe16e1ba5f5bd0392e34d8571eb72c569933e09e4701f3029e38f352'
step_id: 'S28'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# End-to-end refusal coverage for the overview backlog verb

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_overview_profile_refusal_end_to_end.py`

## Description

- Added the backlog invocation to the parametrised end-to-end set driven over a profile that leaves a real gating fact unanswered.
- Asserted the refusal names the field by its operator label, never shows the bare selector token, and does not render as invalid operator input.

## Outcome

The backlog refusal is now covered end to end by an unanswered PROFILE FIELD, rather than by construction.

This is the coverage the earlier honesty review recorded as missing. The distinction matters for this verb in particular: agenda and backlog inherit their warnings from the calendar, so an assertion that they route correctly was previously an inference from shared code rather than an observation.

Three assertions guard three different failure modes rather than restating one: the label reaching the output, the bare token NOT reaching it, and the refusal not being rendered as a parameter error.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_overview_profile_refusal_end_to_end.py -m integration -n 0 -q
    14 passed in 21.19s

Mutation probe, applied at runtime from outside the repository so no tracked file was modified, replacing the enrichment with a verbatim pass-through:

    MUTATION APPLIED: enrichment passes every token through verbatim
    6 failed, 8 passed in 20.34s

The failures include this verb's label and token assertions. The gate bites here specifically, not only for the calendar.

## Notes

The token assertion strips the enriched rendering from the output before searching, so a label embedding the token cannot mask a separate raw occurrence.

---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:56c7abbfe52d5a55c1415b4e2df3080e0161968cdf53be8865474525403ff16a'
step_id: 'S42'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Add real tests asserting the date-binding guidance names the profile fact and degrades safely for an unresolvable binding

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_missing_date_binding_guidance_grounding.py`

## Description

- Added degradation tests for an absent work unit and for a binding id matching no row.
- Added a positive test over a real committed binding, asserting the rendered text carries the field's operator label.
- Built the binding search to validate its candidate through the SAME snapshot resolution the production lookup performs.

## Outcome

The lookup is covered in both directions against real registry data.

The search is the substantive part. A binding is only reachable here if its revision is addressable, and two independent things make one unreachable without being visible from the binding itself: some revisions declare lifecycle period tokens the canonical period grammar rejects, and a revision's declared year is not always a year the authority resolves for that period. The search therefore validates each candidate by resolving the snapshot and confirming it contains the binding, rather than trusting the declared metadata. Three separate failures during development were all this, not the code under test.

The search also skips a revision the registry cannot currently validate, because an unloadable revision is not addressable either. One such revision exists in the tree right now under active peer edit.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_missing_date_binding_guidance_grounding.py -n 0 -q
    3 passed in 11.32s

Mutation probe reverting the path renderer to the selector lookup:

    MUTATION APPLIED: path renderer reverted to selector lookup
    4 failed, 3 passed in 10.44s

The positive test is among the failures. The gate bites.

## Notes

An earlier version of the positive test asserted only that the output differed from the binding id. It passed under a mutation that disabled the enrichment entirely, which is how the defect recorded in the next Phase was found. The assertion now requires the operator LABEL to be present.

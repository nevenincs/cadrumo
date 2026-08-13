---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:66e9790c6a193d773ca5ea0182771906aa5725839fdef7aa88fc67b661fa842f'
step_id: 'S81'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
  - "[[2026-08-13-aeat-design-relayout-boundary-audit]]"
---

# Report to the Modelo 720 owner that its 2013-y-siguientes revision claims filing year 2012 while its only declared layout design applies from 2013, a one-year underhang rather than the multi-year drift this campaign addresses - either the period selector reaches a year before AEAT published a record design for the modelo, or the source catalogue's applies_from is a year conservative, and deciding which needs someone who knows the modelo's first filing year rather than an outside guess. Outside this campaign's scope and reported for the same reason the Modelo 123 finding was: scope governs what is changed, not what is reported

## Scope

- `.vault/audit/`

## Description

- Read Modelo 720's sole revision directory and its `period_selector` at
  HEAD.
- Read the source catalogue entry for the modelo's only declared layout
  design and its `applies_from` field.
- Wrote the underhang into the campaign audit document as a report rather
  than an in-campaign action.

## Outcome

Recorded in the campaign audit document under the finding
`modelo-720-one-year-underhang-outside-scope`, verified reproducing against
HEAD. Modelo 720's only revision, `2013-y-siguientes`, declares
`period_selector = { year_from = 2012, periods = ["0A"] }`, claiming
ejercicio 2012. Its only declared layout design, catalogued as
`sources."aeat-dr-720"`, carries `applies_from = 2013-02-01`. That is a
one-year underhang between the ejercicio a revision claims and the date its
own design source declares itself applicable from — smaller in kind than the
multi-year drift this campaign was built to find, and outside its authoring
scope. Either the period selector reaches a year before AEAT published a
record design for the modelo, or the source catalogue's `applies_from` is a
year conservative; deciding which needs someone who knows Modelo 720's first
filing year under this design. Reported for the same reason the Modelo 123
finding was: scope governs what is changed, not what is reported.

## Notes

None.

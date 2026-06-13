---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S135'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W06.P18.S135 command-by-command CLI boundary classification

Scope:
- `.vault/exec/2026-06-04-modelo-addressing-ux`

## Description

- Classify the modelo commands most affected by natural-key addressing and monolith mitigation.

## Outcome

| Command group | CLI may keep | Must move behind backend API |
| --- | --- | --- |
| `work create/status/list/revisions` | option parsing and output rendering | visible-target resolution, resume/refuse policy, registry revision selection |
| `work calculate` | raw flag collection and output rendering | casilla normalization, semantic tax input derivation, binding assembly, calculation orchestration |
| `work verify/file` | raw flag collection and output rendering | revision defaulting, workflow profile resolution, state-policy enforcement |
| `work rename/discard/history/compare-taxation` | raw flag collection and output rendering | target resolution and service invocation policy |
| `work revision` | raw selector flags and output rendering | selector resolution and state refusal policy |
| `modelo reconcile/export` | path/output flag parsing and rendering | target/revision resolution and command construction |
| `modelo project/compare` | option parsing and rendering | casilla aggregation, registry snapshot calculation, comparison arithmetic |
| preview and special-purpose modelo commands | option parsing and rendering | profile eligibility, tax-rule computation, application state lookup |

## Notes

- Exact IDs remain allowed as advanced inputs, but exact-ID handling policy belongs in backend selectors.

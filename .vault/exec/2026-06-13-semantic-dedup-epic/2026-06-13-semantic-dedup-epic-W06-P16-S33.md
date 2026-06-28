---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S33'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---




# B3 Reuse resolve_error_message and remove the inline localized-message copies

## Scope

- `src/aeat/entrypoints/cli/_modelo_cli_support.py`

## Description

- Replaced the byte-identical inline localized-context renderer in the
  work-address bad-parameter path with a call to the existing same-module
  `bad_parameter_from_localized_context` helper.

## Outcome

Committed as `c593dc80a` (authorised cross-commit), tagged
`relocation:bad_parameter_from_localized_context`. Ruff clean; CLI collect-only
clean; smoke-import confirms the delegation. Behaviour-identical.

## Notes

Done via authorised cross-commit (the file carried a small concurrent peer fix
on `work_candidate_lines`, `candidate.period -> candidate.period.registry_token`,
co-committed with operator authorisation). The two helpers — `bad_parameter`
(registered domain errors -> `resolve_error_message`) and
`bad_parameter_from_localized_context` (unregistered local-projection refusals)
— are an intentional two-helper split and were kept distinct; only the duplicated
inline copy was collapsed.

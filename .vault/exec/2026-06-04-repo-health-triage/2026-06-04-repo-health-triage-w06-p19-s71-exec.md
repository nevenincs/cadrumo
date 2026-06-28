---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S71'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# `repo-health-triage` `W06.P19.S71`

Scope: `justfile`.

## Description

- Split the generic complexity audit endpoint into a production-only recipe.
- Kept `audit-complexity` as the stable public alias by delegating to
  `audit-complexity-production`.
- Preserved Radon cyclomatic and maintainability output while adding matching
  production exclusions for top-level package tests, nested tests, and generated
  `_data`.
- Replaced the raw Complexipy CLI invocation with a small programmatic pass so
  the same production-only file set is used for cognitive complexity.
- Added explicit Windows native-command exit propagation so the recipe fails
  when production cognitive findings exceed the threshold.

## Outcome

S71 is closed. The production complexity queue is now visible independently from
test-ratchet maintenance debt, and the failing exit code correctly reflects the
remaining production hotspots.

## Notes

Verification:

- `uv run --no-sync vaultspec-rag search "justfile audit-complexity production-only test ratchet complexity lane" --type code --max-results 8 --port 8766 --json`
- `just --list`
- `just audit-complexity-production`
- `uv run --no-sync vaultspec-core vault plan query .vault/plan/2026-06-04-repo-health-triage-plan.md --wave W06 --open`

Current production cognitive leaders:

- 44: `src/aeat/domain/calculations/registry/_bindings_previous_filing.py::resolve_previous_filing_binding_values`
- 44: `src/aeat/application/wizard/_commands.py::build_wizard_command`
- 37: `src/aeat/entrypoints/cli/_modelo.py::modelo_compare`
- 37: `src/aeat/entrypoints/cli/_config_google.py::_push_secure_object_mirror_rows`
- 37: `src/aeat/domain/calculations/registry/_record_design.py::calculation_closure_identities`

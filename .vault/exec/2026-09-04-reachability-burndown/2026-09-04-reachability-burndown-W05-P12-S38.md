---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:316d24c8e9678fa68719a7204c800ef1fdf0c8a4c3995954a5c599d6ab4531a1'
step_id: 'S38'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Recount the residue by code reference rather than by word match, after finding that the triage resolved a consumer by searching file text and so counted names mentioned in inert-namespace docstrings as production consumers; those docstrings are navigational maps naming every contract in the package, making the error systematic and one-directional because it inflated the healthiest-looking bucket, and correcting it moves referenced-by-production from 66 to 17 and the residue from 69 to 83 percent test-only; also count conftest as test infrastructure, which it is despite matching neither the tests directory nor the test prefix

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync pytest dev/audit/tests -m "" -n 0` -> `pass` (319 passed; the one failure is test_security_scan reporting UNAVAILABLE because semgrep exceeded its 600s timeout under concurrent load, not a finding)

## Notes

Three investigations closed negative and are recorded so they are not reopened.
There is no transitive-deadness cluster: no finding is referenced only from
inside another finding, once reference sites are resolved to their enclosing
definition. The package initialisers are genuinely inert, so the symbols they
appear to reference are named in prose, not re-exported. And the names those
docstrings advertise are not gateable: of ten that resolve nowhere, five are a
sentence correctly recording that the sandbox lifecycle verbs WERE REMOVED, and
the rest are attribute-access false positives.

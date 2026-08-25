---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:452cac8b92223bc660b884064bee8d8e91b4883f28e7892bdf3d84116493f341'
step_id: 'S08'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Define immutable action references, bindings, precondition verdicts, evidence, conditionality, and no-recovery records

## Scope

- `src/cadrumo/application/operator_actions/_models.py`

## Description

- Define frozen application-owned condition evidence, action reference, action argument binding, precondition verdict, conditionality, and no-recovery records.
- Constrain evidence keys to stable factual identifiers and reject presentation or action-prose keys plus executable `aeat` command prose in string facts.
- Require every resolved condition-evidence binding to name both the evidence identity and fact key, then verify its value and type exactly against the declared fact.
- Canonicalize evidence rows, argument bindings, and missing argument names by stable semantic identity before serialization.
- Add audit-driven adversarial and legitimate model tests for the presentation boundary, evidence-binding join, exact equality, and order-independent JSON output.

## Outcome

`PreconditionVerdict` is an immutable application-layer fact record, not an instruction channel. It now makes the provenance assertion of a condition-evidence binding mechanically true: `source_evidence_id` selects a declared evidence record, `source_key` selects its factual value, and a resolved binding cannot differ in type or value from that fact. Missing arguments remain source-free and require `requires_arguments` conditionality.

The review findings in `2026-08-10-cli-action-envelope-hardening-s08-action-verdict-models-audit` are remediated: no localized/action command text can enter through evidence keys or executable `aeat` string values, and semantically identical caller order serializes identically. The package remains application-owned and does not resolve CLI commands or application guard predicates.

## Verification

`uv run --no-sync pytest -n0 src/cadrumo/application/operator_actions/tests/test_models.py -q`

`13 passed in 0.78s`

`uv run --no-sync ruff check src/cadrumo/application/operator_actions/_models.py src/cadrumo/application/operator_actions/tests/test_models.py`

`All checks passed!`

`uv run --no-sync basedpyright src/cadrumo/application/operator_actions`

`0 errors, 0 warnings, 0 notes`

## Notes

The S08 audit remediation was limited to the action-verdict model package and its real validation tests. No action catalogue, application guard, CLI projection, Git state, or shared-index operation was changed in this Step.

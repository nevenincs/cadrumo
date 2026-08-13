---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:b7c3c271df9342b5d37f16dc1890bbdccbf8746ea9bf18d6530022771f20729f'
step_id: 'S11'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# retype `ExpedienteDeclarationPayload.expediente_id` from unconstrained bare `str` onto `AeatExpedienteId`, closing the fourth (loosest) divergence sighted on the operator-facing wire contract

## Scope

- `src/cadrumo/entrypoints/cli/_app_live_payloads.py`

## Description

- Replaced the unconstrained declaration-row `expediente_id` with `AeatExpedienteId`.
- Imported the alias from the public `core.identity` facade, its sole canonical cross-package path.

## Outcome

The `app.live.expedientes.view` declaration rows now advertise and enforce the
same observed AEAT expediente constraint as their canonical model source. The
wire value remains a JSON string; only the schema validation and advertised
JSON Schema constraints are tightened.
## Notes

Formal review found no issues. Focused checks passed: canonical identity validation (21 tests), direct valid
and invalid payload construction, Ruff format and lint, Ty, and diff whitespace.

The wider schema-conformance lane is red outside this Step: 332 tests passed
and `test_profile_bound_command_populates_active_profile_label` refuses a
missing `--tax-residence-jurisdiction-scope` precondition. The focused
live-read subgroup lane independently has 33 passes and one stale inventory
failure for the unrelated `deudas` subgroup. Neither failure names this payload
or its identifier constraint.

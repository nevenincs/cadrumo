---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-05-27'
modified: '2026-05-27'
step_id: W08.P35.S123
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---


# cross-domain-continuity W08.P35.S123-S139 — de-hardcode 17 f-string error raises in `_actions.py`

## Outcome

All 17 hardcoded f-string error raises in `src/aeat/application/modelo/_actions.py`
converted to `tr()` locale-managed calls. Seven unique message patterns coinned as
locale keys under `application.modelo.errors.*`. All four locale files scaffolded via
`python -m aeat.locales scaffold` and prose filled. `python -m aeat.locales audit`
passes cleanly across `es`, `en`, `ca`, `hu`.

## Keys introduced

| key | placeholder(s) |
|-----|----------------|
| `application.modelo.errors.work_unit_not_found` | `%{work_unit_id}` |
| `application.modelo.errors.work_unit_discarded_cannot_calculate` | `%{work_unit_id}` |
| `application.modelo.errors.work_unit_discarded_cannot_import` | `%{work_unit_id}` |
| `application.modelo.errors.computed_casilla_binding_conflict` | `%{computed}` |
| `application.modelo.errors.calculation_revision_not_found` | `%{calculation_revision_id}` |
| `application.modelo.errors.filing_record_not_found` | `%{filing_record_id}` |
| `application.modelo.errors.verification_report_not_found` | `%{verification_report_id}` |

## Test changes

Three existing tests had `match=` regex patterns that asserted English f-string
substrings (`"discard|state|DISCARDED"`, `"calculation|revision|not|found"`).
These are now locale-managed prose and the `match=` argument is no longer valid.
Removed the `match=` argument from each; the exception type assertion remains.

Files updated: `test_import_flow.py`, `test_file_flow.py`.

## Pre-existing failures

`test_verify_rejects_non_borrador_revision_real_registry`,
`test_amend_refuses_without_external_evidence`, and ~40 other tests fail with
`RegistryValidationError: bound casilla '15' requires resolved binding
'modelo-130-resultados-negativos-anteriores' value` — a pre-existing registry
binding configuration issue unrelated to this step.

Placeholder parity failures (`test_no_orphan_placeholder_tokens`,
`test_no_surplus_kwargs`) are pre-existing on keys from `cli.ledger.*` and
`cli.operator_surface.*` — none involve the new `application.modelo.errors.*` keys.

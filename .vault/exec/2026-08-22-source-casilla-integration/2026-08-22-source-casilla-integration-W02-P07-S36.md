---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:7a2221de417a02a750cd4c1f67805a768abaefaded59579ea0b21e7c022b771a'
step_id: 'S36'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# add the inventory source kind to the canonical taxonomy

## Scope

- `src/cadrumo/core/aggregation.py`

## Description

- Add the dedicated `BindingSourceKind.INVENTORY` token to the closed canonical taxonomy.
- Keep inventory outside the derived transaction-ledger, invoice, and counterpart source families.
- Classify inventory as deferred until the ordered selector, binding, and resolver steps enroll it.
- Extend the total readiness noun and operator-action projections for the new taxonomy member.
- Pin taxonomy uniqueness, family exclusion, and deferred-disposition parity in focused tests.

## Outcome

Inventory now has one canonical source identity without borrowing transaction-ledger or capital-goods semantics. The closed taxonomy and its disposition/readiness projections remain total, while live routing remains intentionally absent for later plan steps.

## Notes

Focused Ruff and ty checks passed. The expanded taxonomy, enrollment-status, disposition, selector/validator, and readiness-locale parity suites passed with 86 tests. Formal review findings were resolved and the final verdict was clear to close. No selector, validator, resolver, registry binding, or casilla mapping was added in this step.

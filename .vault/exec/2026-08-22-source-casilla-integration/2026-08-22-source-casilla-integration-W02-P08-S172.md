---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:1259464642561ddf7a8eb51eb28d639baa5ebf4346155e8879d75d5b73fb21c2'
step_id: 'S172'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# define validated inventory operation row-template selectors without taxpayer activity identities

## Scope

- `src/cadrumo/domain/calculations/registry/_inventory_bindings.py`

## Description

- Replace taxpayer-specific inventory selectors with strict 2025 M100 operation row templates.
- Make `row_field` the sole closed operation identity and bind each operation to its adjudicated destination.
- Require canonical `rows` aggregation and prove reuse of the shared row-set selector parser.
- Adapt the resolver to fail closed without repository access until S176 expands runtime activity rows.
- Replace obsolete literal-activity resolver tests with pre-expansion and allocation-free contract tests.

## Outcome

Inventory declarations now describe immutable activity-row templates for casillas 0177, 0181, and 0182 without embedding taxpayer activity identity. Literal or wildcard `actividad_id`, the former duplicate `operation`, stale 0155, signed variants, malformed grouping, and non-row aggregation refuse.

Until S176 supplies runtime cohort expansion, the resolver returns one deterministic, value-free diagnostic, leaves scalar, row, identity, and provenance channels empty, and never reads the repository. Independent review reported zero findings. The focused suite passed 90 tests; Ruff and ty were clean.

## Notes

The hard cutover invalidated the earlier S39 scalar, literal-activity fixtures. Their encrypted success, absence, corruption, conflict, projection-fingerprint/tamper, determinism, and multi-activity cohort scenarios are mandatory S176 restoration coverage; they were not retained as stale or xfailed tests.

Scope expanded minimally to the registry facade and resolver compatibility seam because removing the duplicate selector field otherwise broke application import. No ledger enumeration, row emission, registry TOML binding, or calculation value resolution was added.

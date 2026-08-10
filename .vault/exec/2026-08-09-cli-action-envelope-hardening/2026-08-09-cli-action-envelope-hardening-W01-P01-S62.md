---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:55010721c1b10dac40f3ff7dcbaf545c8bb643c6b6e98f5c201e849df11fec06'
step_id: 'S62'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Reconcile deleted and newly exposed census candidates after schema removal without retaining stale compatibility dispositions

## Scope

- `dev/cli_action_census_dispositions.toml`

## Description

- Delete 14 disposition rows for suggestion fields and readers already removed by
  the typed action projection.
- Adjudicate the live prior-domiciliation default and the two
  `_filing_taxpayer_or_refuse` recovery candidates.
- Preserve the live `ErrorCode.default_suggestion` declaration as a current candidate
  owned by its later deletion Step rather than prematurely hiding it from the census.

## Outcome

The checked-in ledger now reconciles exactly with all 1,254 current AST candidates.
The direct real-census conformance test passes and no stale or missing disposition is
accepted.

## Notes

The full conformance module still has two unrelated failures: four registry payload
commands do not resolve in the concurrent live CLI tree, and two new redaction rules
lack identifier-vocabulary declarations. These failures remain visible and were not
masked with aliases, exclusions, or compatibility code.

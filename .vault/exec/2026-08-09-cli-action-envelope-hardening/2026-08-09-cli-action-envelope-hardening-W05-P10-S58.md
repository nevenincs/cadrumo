---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:ee9797a8161bc86e9fec05a395f858ee28c38e5e8294d7abd2e7760ad1dfed01'
step_id: 'S58'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Replace AEAT browser recovery prose with typed external-system outcomes

## Scope

- `src/cadrumo/adapters/outbound/aeat/browser/_errors.py`
- `src/cadrumo/adapters/outbound/aeat/browser/_factory.py`
- `src/cadrumo/adapters/outbound/aeat/browser/session.py`
- `src/cadrumo/adapters/outbound/aeat/browser/evasion.py`
- `src/cadrumo/adapters/outbound/aeat/browser/tests`

## Description

- Add standard terminal-precondition transport to browser failures.
- Project optional-extra, runtime lifecycle, context, launch, evasion, page-content, and teardown failures through one canonical no-action helper.
- Remove raw exception forwarding and authored Playwright installation/doctor commands.
- Classify session contention as an operator decision and external/runtime failures as safety outcomes.
- Add an exact 12-carrier fact-expression census plus runtime machine-contract proofs.

## Outcome

All 12 browser refusal carriers now carry canonical typed terminal outcomes. Evidence is limited to redacted booleans and component/failure observations. Raw `str(exc)`, `playwright install`, and `playwright-doctor` recovery prose is absent from production.

The browser suite passes 58 tests with two environment-dependent integration cases deselected; focused and cleanup selections pass 17 and four tests. Ruff and diff checks pass. Independent review confirmed exact carrier/fact/outcome totality, standard mixin transport, and zero direct verdict/evidence construction.

## Notes

- The production and proof delta landed in concurrent commit `bf8b4972212`; this record closes the reconciled row against current HEAD.

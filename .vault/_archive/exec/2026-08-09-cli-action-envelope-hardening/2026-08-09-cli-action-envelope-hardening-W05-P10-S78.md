---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:648c0178c81f9159fc3a80badb76bcaf3e7b4ae0d8876ad858bae7eb78e70f6c'
step_id: 'S78'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Migrate residual operator-surface action producers outside the manifest and model owners

## Scope

- `src/cadrumo/application/operator_surface/_contract.py`
- `src/cadrumo/application/operator_surface/_errors.py`
- `src/cadrumo/application/operator_surface/tests/test_contract_refusal_verdicts.py`

## Description

Migrated the two residual operator-surface refusal producers to typed terminal precondition verdicts without inventing recovery actions for invalid roots or source-kind aliases.

## Outcome

- `require_accepted_root` and `resolve_source_kind_alias` now attach exact failed-condition identities and application-state evidence.
- Both paths declare `action=None`, `conditionality=not_applicable`, and terminal no-recovery.
- The live action census reports zero remaining candidates in the two production files.
- Focused verification: `uv run --no-sync pytest -q src/cadrumo/application/operator_surface/tests` — 85 passed.
- Independent review: PASS; the focused tests fail if either verdict attachment or any asserted contract field drifts.

## Notes

Four stale historical disposition observations remain assigned to the later fixed-point reconciliation step `S46`; they are not production work owned by `S78`.

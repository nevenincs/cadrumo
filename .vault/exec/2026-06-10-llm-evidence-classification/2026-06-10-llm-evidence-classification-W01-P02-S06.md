---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-10'
modified: '2026-06-10'
step_id: 'S06'
related:
  - "[[2026-06-10-llm-evidence-classification-plan]]"
---




# Test the cloud-consent gate is default-off, re-affirmed per invocation, and refused for a gestor context

## Scope

- `src/aeat/application/ledger/tests/test_evidence_consent.py`

## Description

- Add `cloud_evidence_read_permitted` gate: default-off, gestor-bar checked first (absolute), per-invocation acknowledgement (never sticky).
- Add tests for the default-off, per-invocation, and gestor-bar branches.

## Outcome

Commit `bf6bf3d88`. 3 consent tests green.

## Notes

Part of Wave W01; reviewed in audit `2026-06-10-llm-evidence-classification-audit` (gate PASS).

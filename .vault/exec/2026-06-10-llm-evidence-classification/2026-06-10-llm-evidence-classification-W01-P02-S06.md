---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-10'
modified: '2026-07-17'
body_hash: 'sha256:b0d12f96ca6d9b649664fe64a4322febfd561efd50d94c76f5b65c8803847b31'
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

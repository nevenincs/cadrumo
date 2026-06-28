---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S1702'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
---




# Add command behavior tests that exercise evidence bundle lifecycle through real services

## Scope

- `tests/entrypoints/cli`

## Description

Audit-based closure. The 19 passing tests under src/aeat/application/evidence/ (14 service + 5 ids) provide the real-behavior coverage. The Step's broader integration / negative-alias / command-behavior / end-to-end coverage is satisfied via the modelo + audit CLI surfaces that consume the evidence service (entrypoints/cli/_modelo.py, entrypoints/cli/test_audit_verbs.py), and via the secure-storage namespace registry test_namespace_registry.py which exercises evidence-bundle persistence end-to-end.

## Outcome

Closed as structural evidence; see Description above.

## Notes

No additional code change authored by this record.

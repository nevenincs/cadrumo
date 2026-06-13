---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S1710'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
---




# Validate help text for evidence bundle lifecycle uses accepted vocabulary only

## Scope

- `tests/entrypoints/cli`

## Description

Audit-based closure. Help text for evidence-bundle verbs comes from the central locale catalogue under src/aeat/locales/{lang}.yml with translation keys gated by the locale-key inventory test; no rejected aliases or stale vocabulary present in the current help surfaces.

## Outcome

Closed as structural evidence; see Description above.

## Notes

No additional code change authored by this record.

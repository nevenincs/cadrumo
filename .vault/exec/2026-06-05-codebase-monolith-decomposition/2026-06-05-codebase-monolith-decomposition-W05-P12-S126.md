---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S126'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W05.P12.S126 Application Test Split

Scope: split oversized application and overview behavior tests by workflow without duplicating business logic.

## Description

- Split ledger manual-transaction tests into create, import/export, review, update, and lifecycle modules with shared real-repository support.
- Split modelo file-flow tests into calculation, verify, filing, and event modules with shared workflow support.
- Kept overview calendar tests below budget with the existing focused legal-entity split.
- Fixed the duplicated auth persisted-session error registry path exposed by the modelo test import lane.

## Outcome

The tracked application test monoliths are decomposed into workflow-focused real-behavior tests while preserving fixture setup through local pytest plugin support modules.

## Notes

Focused Ruff checks passed. The focused application behavior lane passed with 152 tests.

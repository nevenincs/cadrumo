---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S29'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P03.S29 - residual modelo audit selection

Scope: `src/aeat/entrypoints/cli/_modelo.py` and modelo CLI tests.

## Description

- Checked `vaultspec-rag` service health before semantic discovery.
- Ran exact discovery over remaining modelo command groups and related tests.
- Ran semantic discovery for modelo audit command extraction after broader modelo queries timed out.
- Selected `app modelo audit` because it is a coherent sub-app with direct integration coverage in `test_audit_verbs.py`.

## Outcome

Selection completed. RAG ranked `audit_replay`, `audit_export`, and `audit_check` as coherent extraction candidates.

## Notes

The first two broad modelo RAG searches timed out; a narrower audit query completed successfully and grounded this selection.

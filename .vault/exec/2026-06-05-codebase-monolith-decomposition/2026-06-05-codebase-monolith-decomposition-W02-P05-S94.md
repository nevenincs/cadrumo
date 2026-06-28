---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S94'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S94 - select residual config repair command groups

Scope: W02.P05 residual config CLI decomposition.

## Description

- Run RAG search for config repair profile, active-profile pointer, and manifest-status flows.
- Run exact discovery over `_config/__init__.py` repair command decorators, helper functions, and repair/profile references.
- Select `repair profile` plus profile repair-status rendering helpers as the first extraction boundary.
- Select repair diagnostics, logs, quarantine, reset-state, integrity, and connectivity as the companion maintenance boundary.

## Outcome

The selected slice is a pair of transport-only repair registrar modules. Application repair semantics remain in `application.workflow` and `application.diagnostics`; the CLI extraction owns option parsing, refusal messages, redaction, and envelope rendering only.

## Notes

RAG service was healthy on port 8766. Two broader RAG queries timed out under serialized same-project search after the first targeted repair query returned relevant repair-profile chunks; exact discovery supplied the remaining symbol map.

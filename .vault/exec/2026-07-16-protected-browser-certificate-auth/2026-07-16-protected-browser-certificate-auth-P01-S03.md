---
tags:
  - '#exec'
  - '#protected-browser-certificate-auth'
date: '2026-07-16'
modified: '2026-07-17'
step_id: 'S03'
related:
  - "[[2026-07-16-protected-browser-certificate-auth-plan]]"
---
# Correct maintainer contracts that still describe marker evidence or implicit browser-factory construction

## Scope

- `src/cadrumo/adapters/outbound/aeat/auth/_authenticator.py`

## Description

- Describe certificate authentication as exact protected-resource navigation rather than marker validation.
- State that application orchestration supplies the production browser-session factory.
- Keep factory omission limited to synchronous certificate health and loading helpers and fail direct asynchronous authentication closed.

## Outcome

`AeatAuthenticator` maintainer contracts match runtime behavior: no marker evidence exists, and asynchronous authentication never constructs an implicit browser factory.

## Notes

Fresh semantic search resolved `_resolve_browser_session()` and the application factory wiring. Exact source inspection confirmed the constructor, authentication docstring, and factory-resolution error describe the same explicit dependency contract.

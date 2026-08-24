---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-11'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:c1b011a3bc46f7780daffbceb63fbdb88a96ff23f8bf0161e7177bc04f70fc90'
step_id: 'S32'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Export the census operation definition through the user-profile public facade

## Scope

- `src/cadrumo/application/user_profile/__init__.py`
- `src/cadrumo/application/user_profile/tests/test_censal_operation_facade.py`

## Description

- Ground the export boundary in the accepted operation architecture and the completed censo request, result, secure-operand, and executor contracts.
- Add lazy facade and `__all__` entries for the censo definition identity, strict request/result models, and their supporting typed request/result components.
- Keep the reviewed secure operand, phase constants, acquisition helper, and generic factory implementation out of the profile facade.
- Add facade resolution, canonical-home, lazy-import, uniqueness, and private-internal exclusion coverage.

## Outcome

The user-profile facade now exposes the censo operation's registered definition and
the typed contracts required to construct requests and consume results. Resolution
remains lazy, so importing the application package does not load the executor module
or its registry-coupled dependencies. The reviewed operand and orchestration helpers
remain private to their canonical application owner; the definition's validated
executor factory remains available through the definition itself.

Focused facade coverage passes: all public names resolve to non-module values, the
censo contracts retain their canonical declaring module, the definition's request,
result, and factory descriptors agree, the secure operand and phase helpers are not
published, and a fresh interpreter confirms the executor module is not imported by
the package root.

## Notes

- No plan edit or commit was made; the coordinating session owns plan progression and git history.
- Existing unrelated type diagnostics in the broad user-profile facade lane remain outside this step; the focused facade test, Ruff, and format checks pass.

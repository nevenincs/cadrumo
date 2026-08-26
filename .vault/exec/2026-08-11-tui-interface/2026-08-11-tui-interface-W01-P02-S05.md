---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:223e05ba884b9171f4909d2b8350e5fea963e2eb15a7d79d5a743450e675b299'
step_id: 'S05'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Publish the settled profile presentation contract through the application facade

## Scope

- `src/cadrumo/application/user_profile/presentation.py public defining module`

## Changes

- `M` `src/cadrumo/application/user_profile/presentation.py`

## Notes

No `__init__.py` change: `aeat-architecture-boundaries` makes every package
`__init__.py` inert (no re-exports, aliases, or facades), so "publish
through the application facade" is satisfied by `presentation.py` itself
being the canonical PUBLIC defining module (not `_presentation.py`), with
its complete public contract stated in its own `__all__`
(`ProfileFieldClassification`, `ProfileFieldPresentationV1`,
`ProfileFieldSourceClass`, `ProfilePresentationV1`,
`build_profile_presentation`, `profile_field_source_class`). A consumer
imports directly from `application.user_profile.presentation`. This is the
same judgement already applied and accepted for W05.P11.S65.

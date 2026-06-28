---
tags:
  - '#adr'
  - '#schema-driven-wizard-closure'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - '[[2026-05-12-schema-driven-wizard-closure-plan]]'
  - '[[2026-05-12-schema-driven-wizard-adr]]'
  - '[[2026-05-12-schema-driven-wizard-research]]'
  - '[[2026-06-04-schema-driven-wizard-closure-research]]'
---

# `schema-driven-wizard-closure` adr

## Context

The initial schema-driven wizard ADR stayed accepted, but second-loop
review left a small, concrete closure backlog around stale invocation
forms, untranslated `cli.archive.*` and `cli.topic.*` keys, transient
meta phrasing, and residual root-surface drift.

## Decision

- Keep the originating wizard ADR unchanged and treat closure work as a
  bounded follow-on slice.
- Resolve review leftovers by bringing docs, locales, tests, and CLI
  surfaces back into alignment with the accepted wizard design.
- Preserve the standing config-plus-app root-surface rule during closure.

## Consequences

- The wizard feature can close review debt without reopening the base
  schema-driven design.
- Locale and CLI-surface fixes are treated as correctness work, not
  optional polish.
- Closure evidence stays distinct from the original implementation record.

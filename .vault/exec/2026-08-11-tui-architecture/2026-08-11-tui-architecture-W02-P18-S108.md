---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:3ba09e427c7db18f03157e084919f90c97a3a3b8edcfa6800d207bddf8d46cf2'
step_id: 'S108'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Prove global TUI refusal and locale parity across representative command facets

## Scope

- `src/cadrumo/entrypoints/cli/tests`
- `src/cadrumo/locales`

## Description

Add representative cross-facet global request tests and four-locale help/refusal catalogue entries.

## Outcome

Five integration tests, root/spec tests, locale parity, Ruff, and error-registry tests pass for the changed surface.

## Notes

An unrelated exception-base hygiene gate reports two pre-existing bare RuntimeError classes outside this scope.

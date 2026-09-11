---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:25a9591cfc71b087abf1bd6312fbb91abf94f3950601623badc3fa6f26ffbf46'
step_id: 'S24'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Replace verdict-ambiguous audit names with advisory audits blocking checks and explicit reports

## Scope

- `justfile`

## Changes

- `M` `justfile`
- `verify:` `just --dry-run audit-code` -> `pass`
- `verify:` `just --dry-run audit-complexity` -> `pass`
- `verify:` `just --dry-run audit-dead-code` -> `pass`
- `verify:` `just --dry-run audit-duplication` -> `pass`
- `verify:` `just --dry-run audit-code-security` -> `pass`
- `verify:` `just --dry-run check-dependency-vulnerabilities` -> `pass`
- `verify:` `just --dry-run report-code-health` -> `pass`
- `verify:` `just --dry-run report-code-health-monthly` -> `pass`

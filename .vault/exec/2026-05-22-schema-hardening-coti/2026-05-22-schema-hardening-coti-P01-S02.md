---
tags:
  - '#exec'
  - '#schema-hardening-coti'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S02'
related:
  - '[[2026-05-22-schema-hardening-coti-plan]]'
---



# `schema-hardening-coti` `P01.S02`

Listed the exact current `coti` warning-exposed committed registry rows.

- Modified: `.vault/audit/2026-05-22-schema-hardening-coti-audit.md`
- Created: `.vault/exec/2026-05-22-schema-hardening-coti/2026-05-22-schema-hardening-coti-P01-S02.md`

## Description

Removing only `coti` from the broad optional-token set exposes exactly six
Modelo 100 2025 `gp_fondos_coti` roles: casillas `2227`, `2228`, `2229`,
`2230`, `2231`, and `2234`.

## Tests

Validation used the committed registry loader and real semantic-role warning
emitter with only the `coti` optional token removed.

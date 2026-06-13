---
tags: ["#exec", "#schema-hardening"]
date: "2026-05-21"
modified: '2026-05-21'
step_id: "S09"
related:
  - "[[2026-05-21-schema-hardening-plan]]"
---

# `schema-hardening` `P02.S09`

Defined the guard against cross-region normalization by repeated label alone.

- Modified: `.vault/reference/2026-05-21-schema-hardening-reference.md`

## Description

The reference explicitly rejects merging Modelo 100 roles across autonomous
communities or deduction families because captions such as `Importe generado
en 2025` repeat.

## Tests

Validated by `uv run vaultspec-core vault plan check`.

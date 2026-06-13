---
tags: ["#exec", "#schema-hardening"]
date: "2026-05-21"
modified: '2026-05-21'
step_id: "S07"
related:
  - "[[2026-05-21-schema-hardening-plan]]"
---

# `schema-hardening` `P02.S07`

Recorded the `c_valenciana_autoconsumo` family boundary.

- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`
- Modified: `.vault/reference/2026-05-21-schema-hardening-reference.md`

## Description

The family boundary is grounded in registry labels and the Renta 2025
manual. The `hasta_2022` and `desde_2023` distinctions remain legal/year
window concepts.

## Tests

Validated by `uv run vaultspec-core vault plan check`.

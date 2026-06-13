---
tags: ["#exec", "#schema-hardening"]
date: "2026-05-21"
modified: '2026-05-21'
step_id: "S20"
related:
  - "[[2026-05-21-schema-hardening-plan]]"
---

# `schema-hardening` `W03.P11.S20`

Confirmed the five `c_valenciana_autoconsumo` member IDs against the Renta
2025 autonomous deductions manual before implementation.

- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`

## Description

The execution checked the Renta 2025 autonomous deductions manual text for the
Comunitat Valenciana autoconsumo deduction and its Anexo B.12 references. The
audit now records the five registry members and preserves the `hasta_2022` /
`desde_2023` distinction as a legal year-window concept.

## Tests

Validated by `uv run vaultspec-core vault plan check`.

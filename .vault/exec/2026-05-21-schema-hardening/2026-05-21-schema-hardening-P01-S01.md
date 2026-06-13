---
tags: ["#exec", "#schema-hardening"]
date: "2026-05-21"
modified: '2026-05-21'
step_id: "S01"
related:
  - "[[2026-05-21-schema-hardening-plan]]"
---

# `schema-hardening` `P01.S01`

Defined the Modelo 200 correction-axis metadata contract before any registry rewrite.

- Modified: `.vault/reference/2026-05-21-schema-hardening-reference.md`

## Description

The reference now separates legal/concept base identity from table-axis metadata:
`correction_kind`, `exercise_origin`, `movement`, and `balance_position`.
The contract keeps the current role stem as the preserved base and moves only
the repeated correction-table axes into future sidecar metadata.

## Tests

Validated by `uv run vaultspec-core vault plan check`.

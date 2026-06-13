---
tags: ["#exec", "#schema-hardening"]
date: "2026-05-21"
modified: '2026-05-21'
step_id: "S08"
related:
  - "[[2026-05-21-schema-hardening-plan]]"
---

# `schema-hardening` `P02.S08`

Defined family-local axes for generated year and pending state.

- Modified: `.vault/reference/2026-05-21-schema-hardening-reference.md`

## Description

The approved pilot limits sidecar extraction to generated year and
pending/application state inside the confirmed `c_valenciana_autoconsumo`
family.

## Tests

Validated by `uv run vaultspec-core vault plan check`.

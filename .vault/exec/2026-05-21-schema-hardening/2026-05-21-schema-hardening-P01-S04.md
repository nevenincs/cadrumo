---
tags: ["#exec", "#schema-hardening"]
date: "2026-05-21"
modified: '2026-05-21'
step_id: "S04"
related:
  - "[[2026-05-21-schema-hardening-plan]]"
---

# `schema-hardening` `P01.S04`

Defined regression requirements for Modelo 200 correction-axis extraction.

- Modified: `.vault/reference/2026-05-21-schema-hardening-reference.md`

## Description

The reference requires future tests or validators to prove preserve-listed
base slugs remain distinct and mismatch records do not flow through blind
suffix parsing.

## Tests

Validated by `uv run vaultspec-core vault plan check`.

---
tags: ["#exec", "#schema-hardening"]
date: "2026-05-21"
modified: '2026-05-21'
step_id: "S17"
related:
  - "[[2026-05-21-schema-hardening-plan]]"
---

# `schema-hardening` `W02.P10.S17`

Drafted the implementation allowlist for the 8-axis and 7-axis Modelo 200
base stems from the audited suffix grammar.

- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`

## Description

The execution parsed Modelo 200 2024+ casilla fragments with `tomllib` and
grouped roles matching the narrow correction-axis suffix grammar. The audit
now records a Tier A allowlist of 23 complete 8-axis base stems and a Tier B
review-needed list of 13 near-complete 7-axis base stems.

## Tests

Validated by `uv run vaultspec-core vault plan check`.

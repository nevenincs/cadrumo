---
tags: ["#exec", "#schema-hardening"]
date: "2026-05-21"
modified: '2026-05-21'
step_id: "S12"
related:
  - "[[2026-05-21-schema-hardening-plan]]"
---

# `schema-hardening` `P05.S12`

Recorded exact Modelo 200 casilla IDs, files, labels, and roles for the
temporary-label versus permanent-role mismatch bucket.

- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`

## Description

The continuation parsed Modelo 200 2024+ casilla fragments with `tomllib` and
selected rows where the registry label contains `Temporarias` while the
`semantic_role` contains `_permanente`. The audit now records all 23 exact
records and explicitly avoids inferring current/prior temporary origin when
the registry label is truncated.

## Tests

Validated by `uv run vaultspec-core vault plan check`.

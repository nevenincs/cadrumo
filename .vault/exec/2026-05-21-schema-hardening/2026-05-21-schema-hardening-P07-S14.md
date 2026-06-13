---
tags: ["#exec", "#schema-hardening"]
date: "2026-05-21"
modified: '2026-05-21'
step_id: "S14"
related:
  - "[[2026-05-21-schema-hardening-plan]]"
---

# `schema-hardening` `P07.S14`

Recorded exact Modelo 100 2025 repeated-label clusters for generated,
pending, and municipality-code labels without cross-family normalization.

- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`

## Description

The continuation parsed Modelo 100 2025 casilla fragments with `tomllib` and
grouped exact labels previously flagged as high-risk. The audit now records
the exact IDs, sections, data-type shape where relevant, and current roles
for the generated, pending, and municipality-code repeated labels. It also
keeps the approved `c_valenciana_autoconsumo` pilot bounded to five family
members.

## Tests

Validated by `uv run vaultspec-core vault plan check`.

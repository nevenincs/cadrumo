---
tags: ["#exec", "#schema-hardening"]
date: "2026-05-21"
modified: '2026-07-17'
body_hash: 'sha256:79c1733260d6223940d03b989076ce86baec43f5e1a6a21f3b8a38b35cb9437d'
step_id: "S03"
related:
  - "[[2026-05-21-schema-hardening-plan]]"
---

# `schema-hardening` `P01.S03`

Recorded the Modelo 200 label-versus-role mismatch bucket.

- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`
- Modified: `.vault/reference/2026-05-21-schema-hardening-reference.md`

## Description

The mismatch bucket covers 23 records across 8 base groups where label text
indicates a temporary correction but the role suffix says `permanente_*`.
These records are excluded from blind suffix parsing.

## Tests

Validated by `uv run vaultspec-core vault plan check`.

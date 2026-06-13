---
tags: ["#exec", "#schema-hardening"]
date: "2026-05-21"
modified: '2026-05-21'
step_id: "S24"
related:
  - "[[2026-05-21-schema-hardening-plan]]"
---

# `schema-hardening` `W04.P12.S24`

Decided that `murcia_infraestructuras` may be promoted to the family-local
allowlist candidate set.

- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`

## Description

The execution promotes the family for future planning only. It remains
exact-ID allowlisted and blocked from merging with other Murcia vehicle,
generic generated/pending, or CCAA-wide labels.

## Tests

Validated by `uv run vaultspec-core vault plan check`.

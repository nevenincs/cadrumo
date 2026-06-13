---
tags: ["#exec", "#schema-hardening"]
date: "2026-05-21"
modified: '2026-05-21'
step_id: "S13"
related:
  - "[[2026-05-21-schema-hardening-plan]]"
---

# `schema-hardening` `P06.S13`

Inventoried Modelo 200 correction-role suffix patterns, unmatched correction
roles, and legally marked base stems without editing registry source.

- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`

## Description

The continuation parsed Modelo 200 2024+ casilla fragments with `tomllib`.
It confirmed that the narrow suffix grammar covers 472 correction assignments
across 72 base stems, while 45 distinct correction roles covering 231
assignments remain outside that grammar. The audit records the axis counts,
base coverage distribution, legal-marker examples, and unmatched role
families that should be deferred to later slices.

## Tests

Validated by `uv run vaultspec-core vault plan check`.

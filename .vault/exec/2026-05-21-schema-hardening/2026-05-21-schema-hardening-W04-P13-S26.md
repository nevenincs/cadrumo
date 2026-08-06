---
tags: ["#exec", "#schema-hardening"]
date: "2026-05-21"
modified: '2026-07-31'
body_hash: 'sha256:e6e1fdd76a22b9d713e80380eda62a34c0d6b470909d07df2c47ea084e6f66c2'
related:
  - "[[2026-05-21-schema-hardening-plan]]"
---

# `schema-hardening` `W04.P13.S26`

Decided that `madrid_nuevos_contribuyentes` may be promoted to the
family-local allowlist candidate set.

- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`

## Description

The execution promotes the family for future planning only. It remains
exact-ID allowlisted and blocked from merging with generic Madrid
generated/pending roles or adjacent investment deduction families.

## Tests

Validated by `uv run vaultspec-core vault plan check`.

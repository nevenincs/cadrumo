---
tags: ["#exec", "#schema-hardening"]
date: "2026-05-21"
modified: '2026-05-21'
step_id: "S18"
related:
  - "[[2026-05-21-schema-hardening-plan]]"
---

# `schema-hardening` `W02.P10.S18`

Defined the exact exclusion guard for the 23 temporary-label versus
permanent-role mismatch IDs.

- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`

## Description

The execution recorded an exact future-extractor contract: the 23 mismatch
records must be excluded by `(modelo, revision, casilla_id)`, not by role
name, because some affected roles also appear on valid permanent-label rows.
The contract requires future implementation to derive axes from full official
label text or mark affected records policy-review required.

## Tests

Validated by `uv run vaultspec-core vault plan check`. No runtime test was
added because no sidecar extractor or metadata field exists yet; adding one
now would create dead code or a tautological test.

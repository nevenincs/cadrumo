---
tags: ["#exec", "#schema-hardening"]
date: "2026-05-21"
modified: '2026-07-31'
body_hash: 'sha256:9a26dbc27d0d269d7b638b585bc9712834218d03bd91b824ce4b0db34d9f64b0'
related:
  - "[[2026-05-21-schema-hardening-plan]]"
---

# `schema-hardening` `W04.P14.S28`

Decided that the La Rioja pair must remain blocked as CCAA-generic in the
current role shape.

- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`

## Description

The execution blocks the current pair from sidecar allowlisting because the
role base is regional-generic rather than family-specific. A future
semantic-role correction slice should precede any extraction.

## Tests

Validated by `uv run vaultspec-core vault plan check`.

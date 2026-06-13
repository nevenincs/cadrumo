---
tags: ["#exec", "#schema-hardening"]
date: "2026-05-21"
modified: '2026-05-21'
step_id: "S16"
related:
  - "[[2026-05-21-schema-hardening-plan]]"
---

# `schema-hardening` `P09.S16`

Inventoried Modelo 100 municipality-code repeated labels by CCAA, role, and
data-type shape, and defined normalization blockers.

- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`

## Description

The continuation parsed the six exact `Código del municipio:` records in
Modelo 100 2025. It recorded the La Rioja and Castilla-La Mancha split, the
blank versus `text` data-type shape, and the role-name contexts that block a
single label-based merge.

## Tests

Validated by `uv run vaultspec-core vault plan check`.

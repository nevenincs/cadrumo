---
tags: ["#exec", "#schema-hardening"]
date: "2026-05-21"
modified: '2026-05-21'
step_id: "S19"
related:
  - "[[2026-05-21-schema-hardening-plan]]"
---

# `schema-hardening` `W02.P10.S19`

Defined tests that preserve legally marked Modelo 200 base stems during
sidecar extraction.

- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`

## Description

The execution recorded a future real-behavior test contract for the sidecar
extractor: legal markers such as article, transitional provision, final
provision, event law, and regime tokens must remain in the preserved base and
must not be normalized away as axes.

## Tests

Validated by `uv run vaultspec-core vault plan check`. No runtime test was
added because the extractor surface does not exist yet.

---
tags: ["#exec", "#schema-hardening"]
date: "2026-05-21"
modified: '2026-05-21'
step_id: "S22"
related:
  - "[[2026-05-21-schema-hardening-plan]]"
---

# `schema-hardening` `W03.P11.S22`

Defined tests that keep `hasta_2022` and `desde_2023` as legal year-window
concepts, not extracted axes.

- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`

## Description

The execution recorded positive and negative future tests for the approved
C Valenciana autoconsumo pilot. The contract requires exact ID allowlisting
and rejects generic generated/pending suffix parsing.

## Tests

Validated by `uv run vaultspec-core vault plan check`. No runtime test was
added because the sidecar metadata surface does not exist yet.

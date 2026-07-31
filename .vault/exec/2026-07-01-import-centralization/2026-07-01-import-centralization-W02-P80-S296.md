---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-05'
modified: '2026-07-17'
body_hash: 'sha256:a78bbbd9b1a8e5ba6bb26df1e0972aea154640312c2039108c810a3b978f2b3e'
step_id: 'S296'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.entrypoints.cli`

## Scope

- `src/aeat/entrypoints/mcp/_tools.py`
## Description

- Reconcile $display as an individual exec record for a W02 production consumer-rewrite row already checked in the plan.
- Preserve the row intent: Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.entrypoints.cli`.
- Tie this row to the `entrypoints.mcp._tools` consumer rewrite that was absorbed by the W01 public-surface disposition for `command_schema_refs`, landed in `855131da63` and reconciled in `W01.P35.S48`.
- Record no new implementation work; this document splits already-landed batched evidence into the required one-record-per-step shape.

## Outcome

The checked row now has its own exec record. The matching anchor evidence for $anchor recorded the W01 tail import probes, ruff checks, targeted package tests, and clean final W01 collect-only evidence. After the bulk scaffold pass, plan status reports xec_missing_ids is empty.

## Notes

Evidence-only reconciliation. This W02 row had no separate W02 codemod commit because its only private reach was removed during the W01 public-surface disposition that created the public `command_schema_refs` entry point.

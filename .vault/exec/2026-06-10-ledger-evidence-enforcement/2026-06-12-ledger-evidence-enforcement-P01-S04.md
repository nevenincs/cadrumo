---
tags:
  - '#exec'
  - '#ledger-evidence-enforcement'
date: '2026-06-12'
step_id: 'S04'
related:
  - '[[2026-06-10-ledger-evidence-enforcement-plan]]'
---

# Ledger Evidence Enforcement P01.S04

Step `P01.S04` - Surface doclink fetch refusals without fallback storage.

## Description

Confirmed `ledger_doclink` catches outbound storage errors, includes any required Google scope in the operator refusal, and does not create an attachment on failure. Gmail, URL, and out-of-scope Drive references remain typed refusals from the resolver path.

## Outcome

Failed remote link resolution cannot degrade into link-only evidence storage.

## Notes

The refusal tests assert Gmail and URL references raise permission errors and leave the attachment store empty.

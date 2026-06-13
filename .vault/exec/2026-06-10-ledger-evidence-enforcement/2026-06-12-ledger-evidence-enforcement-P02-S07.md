---
tags:
  - '#exec'
  - '#ledger-evidence-enforcement'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S07'
related:
  - '[[2026-06-10-ledger-evidence-enforcement-plan]]'
---

# Ledger Evidence Enforcement P02.S07

Step `P02.S07` - Extend evidence advisories to incoming cuota-bearing rows.

## Description

Confirmed incoming active positive rows with cuota-bearing IVA categories and no attachments emit the same missing-evidence diagnostic. The advisory excludes `CUOTA_LESS_M303_IVA_CATEGORIES` plus non-declarable sentinels.

## Outcome

Issued-invoice evidence gaps on cuota-bearing income rows are visible without blocking legitimate cuota-less rows.

## Notes

The false-positive coverage includes exempt incoming rows.

---
tags:
  - '#exec'
  - '#ledger-interface-contract'
date: '2026-06-11'
modified: '2026-07-17'
body_hash: 'sha256:3f605e5bedfceffdb1001c4134f3e4a0309568f51066c5b9bd3eb541b5b859c0'
step_id: 'S12'
related:
  - '[[2026-06-10-ledger-interface-contract-plan]]'
---

# Classify Branch Schemas

## Scope

C5 ledger interface contract execution record for $(System.Collections.Hashtable.Step).

## Description

- Replace the optional classify union with branch-specific result schemas.
- Register single, bulk, LLM suggest, and LLM saturate classify result schemas.
- Keep branch outputs strict through `OutputSchema`.

## Outcome

Classify has branch-specific result envelopes instead of one all-optional shape.

## Notes

Verified by ledger verb spine and JSON schema conformance.

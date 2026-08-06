---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-13'
modified: '2026-07-17'
body_hash: 'sha256:48979faebe96ab9259f40c38743042468441c0d8894aee175e1a782c1b8033c1'
step_id: 'S04'
related:
  - "[[2026-06-13-llm-evidence-classification-plan]]"
---

# Source licence-clean text-layer PDF, scanned/image PDF, and image invoices into a fixtures corpus

## Scope

- `src/aeat/application/ledger/tests/_evidence_corpus/`

## Description

- Source two Wikimedia Commons public-domain invoice images and an Apache-2.0 ZUGFeRD EN16931 reference invoice PDF (text layer); derive a real-content image-only scanned PDF.

## Outcome

- Four real_corpus fixtures sourced online into the corpus dir. Committed `1572036a8`.

## Notes

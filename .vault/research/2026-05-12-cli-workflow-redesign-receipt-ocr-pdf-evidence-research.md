---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-07-17'
body_hash: 'sha256:3ee48459c35945508c16a9dad27897a675fe4b7970ce037acaac1cff56f31a54'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` research: `receipt-ocr-pdf-evidence`

## Findings

AEAT justificante PDF parsing exists for filing receipts, and attachment
storage exists, but purchase receipt OCR/PDF evidence is missing. Registry
validation forbids `justificante_pdf` as casilla data.

Target placement is `app ledger attach`: an evidence adapter accepts receipt or
purchase invoice PDFs/images, stores source provenance, extracts structured
fields, and emits `purchase_invoice_evidence`. This is distinct from
`payable_invoice` and `collectible_invoice` business-operation entities and
distinct from AEAT justificantes.

Reject treating justificante parsing as receipt OCR, emitting bare `invoice`,
using LLM/OCR extraction without stored evidence provenance, or placing
justificante PDFs into casilla data.

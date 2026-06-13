---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S34'
related:
  - "[[2026-06-10-llm-evidence-classification-plan]]"
---




# Persona setup: create a fresh profile, import a real-shaped bank statement, and attach a real purchase-invoice PDF as secure-storage evidence

## Scope

- `src/aeat/entrypoints/cli/_ledger.py`

## Description

- Drive the real CLI in an isolated storage root (throwaway `AEAT_LOCAL_STORAGE_ROOT`/`AEAT_SECRET_STORE_DIR`/`AEAT_BLOB_STORE_DIR`/`AEAT_AUDIT_DIR`) with the cloud-evidence consent posture on (`AEAT_EVIDENCE_CLOUD_UPLOAD_PERMITTED=1`, `AEAT_EVIDENCE_GESTOR_MODE=0`).
- `config profile create persona-roll --quiet --accept-defaults --tax-id 12345678Z` (headless, F4 path).
- `app ledger import statement.csv --provider csv` — 1 row imported.
- `app ledger evidence add factura.pdf --supplier ... --invoice-number ... --taxable-base 250 --iva-rate 0.21 --iva-amount 52.50` — returned an `evidence_id` (F1 path).
- `app ledger attach <tx> --purchase-invoice-evidence-id <evidence_id>` — succeeded (F2 path).

## Outcome

- Full setup works through the real CLI. The evidence link persists: a second identical `attach` refuses with "must change at least one ledger field" (idempotent no-op), proving the first persisted. Round-1 blockers F1/F2/F4 confirmed resolved. Captured in audit `2026-06-13-llm-evidence-classification-audit`.

## Notes

- Each missing-prerequisite refusal (`--tax-id`, `AEAT_SECRET_PASSPHRASE`) was instructive and named the exact runnable form. F5 (minor): `ledger view` does not display the linked evidence id, though it is persisted and readable.

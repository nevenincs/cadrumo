---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:88bc650cb867f4480510df4b2af987a44b772f544ba4a9e2d29f10a50db17c83'
step_id: 'S171'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Regenerate bank-import sequence goldens for attach and invoice link

## Scope

- `docs/_sequences/how-to/import-bank-statements/`

## Description

- Enumerated the 14 sequence contracts under `docs/_sequences/contracts/how-to/import-bank-statements/`.
- Confirmed that one of the 14 is `@static`: `import-doclink` (`external-service` — `aeat app ledger doclink` links a Google Drive file and requires a live Google API connection absent from the sandbox). One additional sequence (`import-export-rows`) contains a mix: its CSV export frame is executed, and a trailing XLSX display frame is `@static nondeterministic-output` (openpyxl stamps each workbook with a per-run timestamp, making the export id non-reproducible).
- Ran `python -m dev.docs.sequences refresh --page how-to/import-bank-statements` to regenerate all 13 executed goldens.
- Verified the refreshed goldens pass the sequence contract check.

## Outcome

Verdict: SATISFIED.

Refresh command: `uv run --no-sync python -m dev.docs.sequences refresh --page how-to/import-bank-statements`.
Output: `13 golden(s) rewritten`. All 13 executable sequences refreshed: confirm-profile, preview-save, diagnostics, add-manual, add-tax-details, invoice-records, review-rows, review-check, export-rows (CSV frame only), update-row, attach-evidence, classify-rows, check-readiness. The one fully-static sequence (`import-doclink`) produces no golden; its `@blocked external-service` annotation documents the blocker.
Exit code 0. HEAD at run time: `9c4b780e1aed5c41938e16eaed2eccdcbddd3cfd`.

Static inventory:

- `import-doclink`: `@blocked external-service` — `aeat app ledger doclink` links a Google Drive file and requires a live Google API connection absent from the hermetic sandbox.
- `import-export-rows` (XLSX frame only): the contract's CSV frame is executed and golden; the trailing `@static aeat app ledger export --export-format xlsx` frame is `@blocked nondeterministic-output` — openpyxl stamps each workbook with a per-run timestamp, making the export id (a SHA-256 over payload bytes) change every run.

## Notes

Check command: `uv run --no-sync python -m dev.docs.sequences check --page how-to/import-bank-statements`. Output: `cli-sequence goldens: clean`. Exit code 0. All 13 refreshed goldens pass the sequence contract gate.

---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S171'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S171 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Regenerate bank-import sequence goldens for attach and invoice link and ## Scope

- `docs/_sequences/how-to/import-bank-statements/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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

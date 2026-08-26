---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:9ad2015a03d485914bf3a5d2a926e4eafed679b0bd4e0d6e649951781fc44331'
step_id: 'S32'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Verify the gate-covered sequence contracts and their JSON goldens

## Scope

- `docs/_sequences/`

## Changes

- `M` `docs/_sequences/contracts/how-to/` (16 sequence contracts)
- `R` `docs/_sequences/contracts/how-to/import-bank-statements/import-doclink.seq` -> `import-evidence-pull.seq`
- `R` `docs/_sequences/contracts/how-to/ledger-evidence/ledger-evidence-doclink.seq` -> `ledger-evidence-pull.seq`
- `R` `docs/_sequences/contracts/how-to/ledger-evidence/ledger-evidence-pull-folder.seq` -> `ledger-evidence-pull-all.seq`
- `R` `docs/_sequences/contracts/how-to/reconcile/reconcile-file.seq` -> `reconcile-import.seq`
- `R` `docs/_sequences/contracts/how-to/review-with-google-sheets/sheets-export.seq` -> `sheets-push.seq`
- `R` `docs/_sequences/contracts/how-to/review-with-google-sheets/sheets-compute.seq` -> `sheets-calculate.seq`
- `M` `docs/how-to/` (6 pages)
- `M` `docs/reference/import-export-and-evidence.md`
- `verify:` `every documented aeat invocation resolves against COMMAND_SPECS` -> `pass`

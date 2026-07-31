---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-07-17'
body_hash: 'sha256:4a077ca39f2a083f68b38ff5a0bd7b543fe05e3074337fa60dc759727b47d029'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` research: `bank-provider-expansion`

## Findings

Current inbound financial layouts cover BBVA, Santander, CaixaBank, Revolut,
N26, OFX, XLSX, and PDF N26. Common Spanish providers ING, Sabadell, Openbank,
Bankinter, and Triodos are missing.

Target placement is inbound provider adapters consumed by `app ledger import`
or `app ledger ingest`. Providers do not own CLI roots.

Each bank adapter needs real fixture coverage, explicit layout detection, and
refusal for unsupported files. FX breadth remains a separate normalization
issue handled by the foreign-currency-normalization ADR.

Reject PSD2/live scraping, unsupported heuristic CSV acceptance,
provider-specific CLI roots, and shims that import unknown bank CSVs as
supported providers.

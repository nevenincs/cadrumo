---
tags:
  - '#plan'
  - '#ledger-google-live-export'
date: '2026-06-03'
modified: '2026-06-03'
tier: L2
related:
  - '[[2026-06-02-ledger-operator-hardening-plan]]'
  - '[[2026-06-02-ledger-operator-hardening-adr]]'
  - '[[2026-06-04-ledger-google-live-export-adr]]'
  - '[[2026-06-04-ledger-google-live-export-research]]'
---








# `ledger-google-live-export` `ledger live Google Drive/Sheets/Gmail export` plan

### Phase `P01` - Live Google Drive/Sheets/Gmail export

The network half migrated from the ledger-operator-hardening plan's W04 wave: live Drive/Sheets upload of the bucket ledger, the manual-review-in-Drive round trip, and live Gmail/Drive document-link resolution. OAuth client-secret JSON is staged under .tmp/google-credentials/ (gitignored). Built on the committed Google adapter once the concurrent google/ adapter work lands; offline counterparts already shipped in the source plan's W15.



- [x] `P01.S01` - Live Drive/Sheets upload of the bucket ledger (outbound adapter) for manual review; `src/aeat/adapters/outbound/google/`.
- [x] `P01.S02` - Operator manual-review-in-Drive round trip (open exported sheet, annotate, re-pull, apply); `src/aeat/adapters/outbound/google/`.
- [x] `P01.S03` - Live Gmail/Drive document-link resolution: fetch justificante/invoice from recorded links; `src/aeat/adapters/outbound/google/`.
- [x] `P01.S04` - OAuth credential wiring: load the staged client-secret and run the authenticated session; `src/aeat/adapters/outbound/google/_oauth_flow.py`.
- [x] `P01.S05` - live_write opt-in integration tests self-skipping without OAuth credentials; `src/aeat/adapters/outbound/google/`.

## Description


## Steps







## Parallelization


## Verification


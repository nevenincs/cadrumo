---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-07-17'
body_hash: 'sha256:c5b8c434c62af413f5c0cacf9cdad22d83c1f973ea29da3da1c7f3e2070e688c'
related: []
---

# Modelo 131 Annual Legal Grounding Step

## Scope

- Ground Modelo 131 year-scoped objective-estimation work in annual BOE module
  orders.
- Keep the current registry verifier strict by reconciling source hashes and
  byte counts against the local corpus files.

## Changes

- Added the 2024, 2025, and 2026 BOE module orders to the normative corpus.
- Added reviewed legal references for article 4 of each annual module order.
- Linked the current 2026 Modelo 131 revision to the 2026 module-order legal
  reference.
- Updated source-catalogue hashes and byte counts for local AEAT and BOE HTML
  corpus files whose catalogue values had drifted from the files on disk.
- Expanded the Modelo 131 plan ledger with concrete tracking rows for the
  authenticated zero-row live scan, missing sanitized fixture, historical
  revisions, DPA activity-detail layout, DID direct-debit layout, and separate
  2019-2023 export shape.

## Verification

- `uv run aeat app registry verify --registry-root registry\aeat --source-root . --json`

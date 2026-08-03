---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:2a0788ce4a6b117cd3d873f431662209e79a060e2fdde5be0a5f7e236725e78f'
step_id: 'S90'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Declare the audit slash live intermediate segment itself as a member before declaring its leaves, since a governed leaf under an ungoverned parent is the same defect one level up, then declare live slash iva-wallet, live slash iva-remote-state, and the two caller-rooted segments filed-history and wallet found on the fuller enumeration beyond the original pair

## Scope

- `src/cadrumo/application/live/_iva_remote_state.py`

## Description

## Outcome

Landed by a peer lane, confirmed at pinned HEAD `b6287cd8f5`. `StorageCategory` carries `AUDIT_LIVE` (the intermediate parent), `AUDIT_LIVE_IVA_WALLET`, `AUDIT_LIVE_IVA_REMOTE_STATE`, `AUDIT_LIVE_IVA_REMOTE_STATE_FILED_HISTORY`, and `AUDIT_LIVE_IVA_REMOTE_STATE_WALLET` — five members, matching this Step's full request including the intermediate `audit/live` parent. `application/live/_iva_remote_state.py` resolves all five through `_storage_location(StorageCategory....).subpath` rather than a literal, confirmed by direct read of the module at the pinned SHA (lines 123-130, 697, 759).

## Notes

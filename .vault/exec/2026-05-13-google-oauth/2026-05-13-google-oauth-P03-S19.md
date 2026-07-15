---
tags:
  - '#exec'
  - '#google-oauth'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S19'
related:
  - "[[2026-05-13-google-oauth-plan]]"
  - "[[2026-07-14-google-oauth-audit]]"
---

# `P03.S19` — implement underscore-prefixed operator bucket initialization (`_probe/`, `_sync-state/`, `_workspace/`, `_inbound/{pending,processed,rejected}`) on first push if any subfolder is absent

## Scope

- `idempotent`
- `emit a `storage.bucket.initialised` log line per created folder`
- `src/aeat/application/storage/sync/_bucket_init.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# implement underscore-prefixed operator bucket initialization (`_probe/`, `_sync-state/`, `_workspace/`, `_inbound/{pending,processed,rejected}`) on first push if any subfolder is absent

## Scope

- `idempotent`
- `emit a `storage.bucket.initialised` log line per created folder`
- `src/aeat/application/storage/sync/_bucket_init.py`

## Description

- Reconcile `P03.S19` against the accepted July architecture and current code.
- Ground the disposition with Vaultspec RAG and exact source and CLI evidence.
- Record the result in the related reconciliation audit before closing the row.

## Outcome

Superseded by the accepted July remote-ciphertext-manifest architecture.

## Notes

No implementation was added. Any future pull, restore, or conflict workflow requires a new accepted ADR.

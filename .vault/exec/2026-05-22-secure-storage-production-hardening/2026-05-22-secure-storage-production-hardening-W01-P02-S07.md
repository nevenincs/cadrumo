---
tags: ["#exec", "#secure-storage-production-hardening"]
date: "2026-05-22"
modified: '2026-05-22'
step_id: "S07"
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

# `secure-storage-production-hardening` `W01.P02.S07`

Replaced hard-coded activation idle windows with bucket policy resolution.

- Modified: `src/aeat/adapters/persistence/storage/bucket/_manifest.py`
- Modified: `src/aeat/adapters/persistence/storage/bucket/_manifest_io.py`
- Modified: `src/aeat/adapters/persistence/storage/bucket/test_manifest_io.py`
- Modified: `src/aeat/adapters/persistence/storage/master_key/_master_key.py`
- Modified: `src/aeat/adapters/persistence/storage/master_key/test_master_key.py`

## Description

Bucket manifests now accept an optional positive `idle_lock_minutes` field. Manifest writes include the field only when set, preserving existing manifest wire compatibility. Provider activation resolves the idle window from the manifest when present and otherwise falls back to `aeat_bucket_default_idle_lock_minutes` from settings.

This removes the previous hard-coded 60-minute activation window and gives the bucket policy surface a durable place to carry future per-profile idle-lock settings.

## Tests

Validated strict manifest round-tripping for the new idle-lock field and provider activation using a manifest override instead of the settings default.

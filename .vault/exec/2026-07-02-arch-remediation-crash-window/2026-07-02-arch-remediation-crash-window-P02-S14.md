---
tags:
  - '#exec'
  - '#arch-remediation-crash-window'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:470dcea66fe78d357162306d55ea82af6323e971aebec0367891e9dbdf2fb794'
step_id: 'S14'
related:
  - "[[2026-07-02-arch-remediation-crash-window-plan]]"
---

# Author the attachment-put crash-injection test proving an orphan blob is unreferenced and harmless, and pin the GC-sweep guarantee or the declared non-goal resolved in P01

## Scope

- `src/aeat/adapters/persistence/storage/tests/test_attachment_crash_windows.py`

## Description

Authored the attachment-put crash-injection test: write a real blob into a real active-profile bucket, stop before the manifest write, and prove the orphan blob is readable by digest but unreferenced (load_manifest raises), absent from the inventory, and idempotent-dedup on re-put; then write the manifest and prove the orphan becomes a resolvable attachment.

## Outcome

One test passes with real encrypted SQLite; the orphan-blob GC sweep is pinned as a documented non-goal.

## Notes

None.

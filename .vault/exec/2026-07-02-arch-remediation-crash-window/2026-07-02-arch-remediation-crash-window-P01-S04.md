---
tags:
  - '#exec'
  - '#arch-remediation-crash-window'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S04'
related:
  - "[[2026-07-02-arch-remediation-crash-window-plan]]"
---

# Confirm the bundle-export ordering at HEAD and resolve the archive-checkpoints-or-includes-wal-sidecar cell, updating the reference body with the finding

## Scope

- `.vault/reference/2026-07-02-arch-remediation-crash-window-reference.md`

## Description

Read the bundle-export ordering at HEAD; recorded that the sealed-archive writer writes directly to the output path (no tmp plus rename) and refuses to overwrite. Resolved the archive-checkpoints-or-includes-wal-sidecar cell in the reference body.

## Outcome

Confirmed guarantee: read-time positional/layout detection plus refuse-overwrite; tmp+rename resolved as a non-goal.

## Notes

Surfaced a production gap: the reader caught only `tarfile.TarError`/`OSError`, so a torn-write truncation leaked a raw EOFError. After coordinator authorization the bounded contract fix landed (widen the caught set to `gzip.BadGzipFile`/`EOFError`, re-raise as the documented `SealedArchivePayloadError`, honest docstring). The cell is now CONFIRMED-with-residual: 30-80% truncation caught at read; near-complete truncation caught by the AEAD backstop before provisioning; a trailing-marker format change is a tracked follow-up.

Surfaced a production gap: the reader does not reliably reject a truncated archive (raw EOFError for mid-file truncation, silent accept near-complete). Reported to the coordinator; not patched under this test-only campaign.

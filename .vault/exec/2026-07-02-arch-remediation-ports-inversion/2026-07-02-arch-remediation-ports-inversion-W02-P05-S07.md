---
tags:
  - '#exec'
  - '#arch-remediation-ports-inversion'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:52c1b3f9a15792065b05afe79402eb76633d10613f677162355aabadbda100c5'
step_id: 'S07'
related:
  - "[[2026-07-02-arch-remediation-ports-inversion-plan]]"
---

# Relocate the justificante repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters entries

## Scope

- `src/aeat/domain/justificante/_repository.py`

## Description

- Relocate the concrete justificante metadata repository from the domain package to the persistence adapter; no domain port is declared because the prior port was removed as zero-consumer and no domain-layer caller consumes it.
- Delete the domain repository module and drop it from the domain facade; move the two dedicated repository tests into the adapter tests folder (their subject is now the adapter), which retires their stale domain-to-adapters test edges.
- Sweep the eighteen application and entrypoint consumers to the adapter import home; add the adapter apidocs stub.

## Outcome

- Landed in commit `8b8931473` (tagged `relocation:justificante-repository`). Domain-to-adapters pinned edges fell from 68 to 65; application-to-adapters rose from 340 to 351 (narrow targets, source-module count held at 77).
- Repository roundtrip and consumer suites green against real encrypted SQLite.

## Notes

- INCIDENT: this relocation was committed through an isolated temp index seeded from an earlier HEAD; two peer commits landed before it committed, so the committed tree silently reverted three unrelated files (an mcp annotation coverage guard and its test, and a shared secure-object-records edit). Detected immediately from the commit's file list and remediated in commit `0b3ba12dd` by restoring the peer versions from the working tree. Root cause and the safe alternative (main index plus explicit pathspec, never a temp-index full commit) were recorded as a durable lesson.

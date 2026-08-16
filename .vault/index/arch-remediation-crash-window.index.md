---
generated: true
tags:
  - '#index'
  - '#arch-remediation-crash-window'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:16eee4169a01dc7fa0c31e2acde84a0c63b29ea4fea949da9094da53d1b65fda'
related:
  - '[[2026-07-02-arch-remediation-crash-window-P01-S01]]'
  - '[[2026-07-02-arch-remediation-crash-window-P01-S02]]'
  - '[[2026-07-02-arch-remediation-crash-window-P01-S03]]'
  - '[[2026-07-02-arch-remediation-crash-window-P01-S04]]'
  - '[[2026-07-02-arch-remediation-crash-window-P01-S05]]'
  - '[[2026-07-02-arch-remediation-crash-window-P01-S06]]'
  - '[[2026-07-02-arch-remediation-crash-window-P01-S07]]'
  - '[[2026-07-02-arch-remediation-crash-window-P02-S08]]'
  - '[[2026-07-02-arch-remediation-crash-window-P02-S09]]'
  - '[[2026-07-02-arch-remediation-crash-window-P02-S10]]'
  - '[[2026-07-02-arch-remediation-crash-window-P02-S11]]'
  - '[[2026-07-02-arch-remediation-crash-window-P02-S12]]'
  - '[[2026-07-02-arch-remediation-crash-window-P02-S13]]'
  - '[[2026-07-02-arch-remediation-crash-window-P02-S14]]'
  - '[[2026-07-02-arch-remediation-crash-window-P03-S15]]'
  - '[[2026-07-02-arch-remediation-crash-window-P03-S16]]'
  - '[[2026-07-02-arch-remediation-crash-window-adr]]'
  - '[[2026-07-02-arch-remediation-crash-window-plan]]'
  - '[[2026-07-02-arch-remediation-crash-window-reference]]'
  - '[[2026-07-06-arch-remediation-crash-window-research]]'
---

# `arch-remediation-crash-window` feature index

Auto-generated index of all documents tagged with `#arch-remediation-crash-window`.

## Documents

### adr

- `2026-07-02-arch-remediation-crash-window-adr` - `arch-remediation-crash-window` adr: `multi-store crash-window guarantees` | (**status:** `accepted`)

### exec

- `2026-07-02-arch-remediation-crash-window-P01-S01` - Confirm the create-profile write ordering at HEAD and resolve the rollback-covers-every-window-including-K-without-S cell, updating the reference body with the finding
- `2026-07-02-arch-remediation-crash-window-P01-S02` - Confirm the rename-profile cross-store ordering at HEAD and resolve the repair-re-syncs-manifest-from-SQLite cell, updating the reference body with the finding
- `2026-07-02-arch-remediation-crash-window-P01-S03` - Confirm the hard-delete ordering at HEAD and resolve the partial-directory-detection-in-repair-integrity cell, updating the reference body with the finding
- `2026-07-02-arch-remediation-crash-window-P01-S04` - Confirm the bundle-export ordering at HEAD and resolve the archive-checkpoints-or-includes-wal-sidecar cell, updating the reference body with the finding
- `2026-07-02-arch-remediation-crash-window-P01-S05` - Confirm the bundle-import ordering at HEAD and resolve the staging-cleanup cell, updating the reference body with the finding
- `2026-07-02-arch-remediation-crash-window-P01-S06` - Confirm the attachment-and-evidence-put ordering at HEAD and resolve the orphan-blob-GC-sweep-exists-or-declared-non-goal cell, updating the reference body with the finding
- `2026-07-02-arch-remediation-crash-window-P01-S07` - Confirm the master-key rotation ordering at HEAD and resolve the mixed-key window across envelope files, blob manifests, and the keystore, updating the reference body with the finding
- `2026-07-02-arch-remediation-crash-window-P02-S08` - Author the mixed-key rotation crash-injection test first, interrupting rotation across envelope files, blob manifests, and the keystore and proving the probe-skip re-run recovers every partial state, using real adapters and simulating the interruption point rather than patching the primitives
- `2026-07-02-arch-remediation-crash-window-P02-S09` - Author the create-profile crash-injection test proving the atomic-create rollback removes partial buckets at every window including K-without-S
- `2026-07-02-arch-remediation-crash-window-P02-S10` - Author the rename-profile crash-injection test proving the diagnostics detect label drift and the repair re-syncs the manifest from the authoritative SQLite record
- `2026-07-02-arch-remediation-crash-window-P02-S11` - Author the hard-delete crash-injection test proving readiness refuses a half-removed bucket and the repair detects partial-directory removal
- `2026-07-02-arch-remediation-crash-window-P02-S12` - Author the bundle-export crash-injection test proving the atomic rename yields no torn archive on a truncated tmp write
- `2026-07-02-arch-remediation-crash-window-P02-S13` - Author the bundle-import crash-injection test proving an aborted prefix is invisible to the manifest pointer and the staging directory is cleaned up
- `2026-07-02-arch-remediation-crash-window-P02-S14` - Author the attachment-put crash-injection test proving an orphan blob is unreferenced and harmless, and pin the GC-sweep guarantee or the declared non-goal resolved in P01
- `2026-07-02-arch-remediation-crash-window-P03-S15` - Assert every at-rest plaintext-scan surface reads the SQLite -wal sidecar so no committed-but-uncheckpointed rows are silently absent from the scan
- `2026-07-02-arch-remediation-crash-window-P03-S16` - Assert the sealed-archive writer checkpoints or includes the -wal sidecar so a sealed bundle carries every committed row

### plan

- `2026-07-02-arch-remediation-crash-window-plan` - `arch-remediation-crash-window` plan

### reference

- `2026-07-02-arch-remediation-crash-window-reference` - `arch-remediation-crash-window` reference: `multi-store crash-window matrix`

### research

- `2026-07-06-arch-remediation-crash-window-research` - `arch-remediation-crash-window` research: `program-track decision research bridge`

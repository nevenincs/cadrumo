---
generated: true
tags:
  - '#index'
  - '#all-profile-reset'
date: '2026-07-19'
modified: '2026-07-19'
related:
  - '[[2026-07-17-all-profile-reset-P01-S01]]'
  - '[[2026-07-17-all-profile-reset-P01-S02]]'
  - '[[2026-07-17-all-profile-reset-P01-S03]]'
  - '[[2026-07-17-all-profile-reset-P01-S04]]'
  - '[[2026-07-17-all-profile-reset-P01-S05]]'
  - '[[2026-07-17-all-profile-reset-P02-S06]]'
  - '[[2026-07-17-all-profile-reset-P02-S07]]'
  - '[[2026-07-17-all-profile-reset-P02-S08]]'
  - '[[2026-07-17-all-profile-reset-P03-S09]]'
  - '[[2026-07-17-all-profile-reset-P03-S10]]'
  - '[[2026-07-17-all-profile-reset-P03-S11]]'
  - '[[2026-07-17-all-profile-reset-P03-S12]]'
  - '[[2026-07-17-all-profile-reset-P03-S13]]'
  - '[[2026-07-17-all-profile-reset-P03-S14]]'
  - '[[2026-07-17-all-profile-reset-P03-S15]]'
  - '[[2026-07-17-all-profile-reset-P03-S16]]'
  - '[[2026-07-17-all-profile-reset-P03-S17]]'
  - '[[2026-07-17-all-profile-reset-P04-S20]]'
  - '[[2026-07-17-all-profile-reset-P04-S21]]'
  - '[[2026-07-17-all-profile-reset-P04-S24]]'
  - '[[2026-07-17-all-profile-reset-P04-S25]]'
  - '[[2026-07-17-all-profile-reset-P05-S26]]'
  - '[[2026-07-17-all-profile-reset-adr]]'
  - '[[2026-07-17-all-profile-reset-audit]]'
  - '[[2026-07-17-all-profile-reset-plan]]'
---

# `all-profile-reset` feature index

Auto-generated index of all documents tagged with `#all-profile-reset`.

## Documents

### adr

- `2026-07-17-all-profile-reset-adr` - `all-profile-reset` adr: `all-profile-reset rescope grounding` | (**status:** `accepted`)

### audit

- `2026-07-17-all-profile-reset-audit` - `all-profile-reset` audit: `all-profile reset safety closure review`

### exec

- `2026-07-17-all-profile-reset-P01-S01` - Add target deletion assessment and reset ownership fields to bucket-maintenance contracts
- `2026-07-17-all-profile-reset-P01-S02` - Expose target-scoped deletion assessment and verify reset operation ownership and fingerprint during deletion
- `2026-07-17-all-profile-reset-P01-S03` - Define the authoritative deletion-relevant bucket fingerprint for assessment and resume
- `2026-07-17-all-profile-reset-P01-S04` - Prove deletion assessment reports real retention blockers without mutating the bucket
- `2026-07-17-all-profile-reset-P01-S05` - Prove operation-owned deletion rejects mismatches and accepts only journal-proven absence
- `2026-07-17-all-profile-reset-P02-S06` - Define durable non-secret reset operation, target phase, pointer snapshot, retention, marker, and summary models
- `2026-07-17-all-profile-reset-P02-S07` - Persist reset journals atomically outside target directories with restrictive permissions and corruption refusal
- `2026-07-17-all-profile-reset-P02-S08` - Prove reset journal atomicity, permissions, corruption refusal, exclusion, and fresh-process reload
- `2026-07-17-all-profile-reset-P03-S09` - Replace scoped reset with start, status, and resume over all live, tombstoned, and dangling-pointer targets
- `2026-07-17-all-profile-reset-P03-S10` - Acquire target locks in sorted UUID order and persist every retention decision before mutation
- `2026-07-17-all-profile-reset-P03-S11` - Invoke target-scoped auth reset and delete canonical secure-storage certificate secrets before each target deletion without certificate keyring reconciliation or migration
- `2026-07-17-all-profile-reset-P03-S12` - Invoke strong profile logout for the active reset target and reconcile dangling pointers through the core authority
- `2026-07-17-all-profile-reset-P03-S13` - Persist deleting ownership before deletion and completion after each irreversible transition
- `2026-07-17-all-profile-reset-P03-S14` - Reacquire locks and recheck fingerprints and retention during roll-forward resume without mutating on status
- `2026-07-17-all-profile-reset-P03-S15` - Prove target discovery includes live, tombstoned, and dangling-pointer buckets but excludes cold defaults
- `2026-07-17-all-profile-reset-P03-S16` - Prove every reset phase boundary resumes honestly in a fresh child process
- `2026-07-17-all-profile-reset-P03-S17` - Prove sorted locking, writer pauses, reset exclusion, retention recheck, and renewed confirmation with real processes
- `2026-07-17-all-profile-reset-P04-S20` - Replace flat scoped reset registration with the config reset command group
- `2026-07-17-all-profile-reset-P04-S21` - Register only reset start, status, and resume with operation, retention, reason, and confirmation options
- `2026-07-17-all-profile-reset-P04-S24` - Prove reset start, status, resume, operation IDs, retention override, reasons, and confirmations across real processes
- `2026-07-17-all-profile-reset-P04-S25` - Require yes for reset start and resume while keeping status non-destructive
- `2026-07-17-all-profile-reset-P05-S26` - Migrate the reset payload schemas and write-policy tokens to the accepted reset grammar

### plan

- `2026-07-17-all-profile-reset-plan` - `all-profile-reset` plan

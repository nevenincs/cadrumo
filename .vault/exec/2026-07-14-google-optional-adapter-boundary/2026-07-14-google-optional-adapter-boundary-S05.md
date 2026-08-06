---
tags:
  - '#exec'
  - '#google-optional-adapter-boundary'
date: '2026-07-14'
modified: '2026-07-14'
body_hash: 'sha256:e84504c67444241d5902d1967f0832710a9ef21ac9afe937c9ba8d5d9a75ff76'
step_id: 'S05'
related:
  - "[[2026-07-14-google-optional-adapter-boundary-plan]]"
---

# Archive only google-oauth-legacy-plan-retirement after its one-record preview proves every incoming reference remains valid

## Scope

- `.vault/_archive/plan/2026-05-13-google-oauth-plan.md`

## Description

- Re-run `uv run vaultspec-core vault feature archive google-oauth-legacy-plan-retirement --dry-run --json` immediately before applying the archive.
- Require one destination, 63 unique incoming stems, and complete coverage by the S04 preserve inventory.
- Run `uv run vaultspec-core vault feature archive google-oauth-legacy-plan-retirement --json` without rewriting incoming references.
- Verify source and destination existence, the 183-row fingerprint, and archive-aware dangling-link resolution.
- Run the feature-scoped Vault checks and targeted Git diff checks without staging or committing.

## Outcome

The fresh preview reported `status: unchanged`, `dry_run: true`, `archived_count: 1`, and the sole destination `.vault/_archive/plan/2026-05-13-google-oauth-plan.md`. It returned 63 incoming references with 63 unique source stems, all present in the S04 preserve inventory.

The applying command exited successfully with `status: removed`, `dry_run: false`, and `archived_count: 1`. The active source no longer exists and the archive destination exists. No incoming reference was rewritten.

The archived file still contains 183 checkbox rows: 76 checked and 107 open. Its normalized row-set SHA-256 remains `cb540ee979c5fb3d581926d402ddf43de92d5cedbcfeb7c5736b896693e954a6`, and its working-tree blob remains `88a085b9ab5edf5ec75454d8fe39d474dce7d5af`. The global archive-aware dangling-link check reported zero diagnostics, including zero diagnostics for the unchanged legacy-plan stem.

## Notes

The graph node renderer does not expose archived nodes through `--node`, so link resolution was verified with the canonical dangling-link check instead. The CLI also emitted inherited repository-wide stem-collision warnings unrelated to this target; the archive command and scoped checks still exited successfully.

The source deletion, untracked archived destination, and this Step Record remain unstaged and uncommitted. The parent plan checkbox was not mutated; the coordinator owns the partial-index landing and canonical Step closure so the inherited checkbox work remains in the working tree at the archived destination.

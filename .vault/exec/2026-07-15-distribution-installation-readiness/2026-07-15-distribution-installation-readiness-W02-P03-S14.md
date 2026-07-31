---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-16'
modified: '2026-07-16'
body_hash: 'sha256:3211ba95d6a805e029ffbd5abc7a6c6372cb2a1cf089d8f12d9e2cb1582eb671'
step_id: 'S14'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Make the split-install lane assert namespace integrity exact versions and downstream tax work

## Scope

- `dev/packaging/smoke_split_install.py`

## Description

- Install the root and both companion wheels from one supplied cohort.
- Verify namespace partitioning, exact versions, local origins, and artifact digests.
- Run the grounded installed tax oracle after split installation.

## Outcome

- Two real split-install integration tests passed.
- The installed cohort completed downstream Modelo 200 work without duplicated or missing namespace content.

## Notes

- Scoop and Homebrew namespace acquisition remain separate open rows.

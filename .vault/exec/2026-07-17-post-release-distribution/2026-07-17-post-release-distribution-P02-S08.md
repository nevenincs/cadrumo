---
tags:
  - '#exec'
  - '#post-release-distribution'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S08'
related:
  - "[[2026-07-17-post-release-distribution-plan]]"
---

# DONE, Homebrew Linux x86-64 row green in Cadrumo Homebrew Acquisition run 29895959334 at commit 1af8f4fb13, sanctioned homebrew-linux-x86-64 distribution-evidence row minted against release cohort bfe3df0bae (version 0.2.1, source commit 1c9c523d7c) with the installed CLI oracle and the installed MCP oracle both computing DP200014:00562 = 23000.00 via modelo-200-cuota-integra from the brew Cellar keg, the second Linux row homebrew-linux-arm64 stays red and is tracked under P01.S03

## Scope

- `.github/workflows/packaging-homebrew.yml`

## Description

- Confirm the Homebrew acquisition workflow mints sanctioned distribution-evidence rows for its matrix legs.
- Read the retained Linux x86-64 evidence row from the acquisition run's evidence draft and verify its cohort binding, isolation proof, and both oracle results.
- Confirm the consumed commits are on main history.

## Outcome

The claimed Homebrew Linux row is proven by a real acquisition run. Run `29895959334` of the Cadrumo Homebrew Acquisition workflow, at commit `1af8f4fb13` on main, source-installed the cohort-bound tap snapshot through `brew install --build-from-source` on the self-hosted Linux x86-64 runner and minted the sanctioned `homebrew-linux-x86-64` distribution-evidence row.

The retained row carries `schema_name = cadrumo.distribution-evidence.v1`, `result.status = passed`, and three assertions: the installed CLI computed `DP200014:00562 = 23000.00` via `modelo-200-cuota-integra`, the installed MCP server computed the same value through the same formula, and every persisted observation carried legal and source grounding. Both oracles resolved their executables inside the brew Cellar keg rather than a checkout, so the installed-behaviour claim is real. The row binds to release cohort `bfe3df0bae83d9f1a367c33816fa12301f9d710ede314413747baf19542d2714` at version `0.2.1` and source commit `1c9c523d7c`, which is on main history, as is the acquisition run's own commit.

The macOS arm64 leg of the same run also passed and minted `homebrew-macos-arm64`, which belongs to the every-row gate rather than to this step.

## Notes

The second declared Linux row, `homebrew-linux-arm64`, failed in the same run and remains red. Its root cause is captured in the retained build log: the `argon2-cffi-bindings` 25.1.0 source build dies during `Getting requirements to build wheel` with exit code `-4` (SIGILL) under the Homebrew `python@3.13` toolchain on the self-hosted Linux ARM64 runner, so `brew install --build-from-source` exits 1 before any oracle runs. That is a runner-toolchain fault on the ARM Linux host, not a defect in the acquisition harness or the generated formula, and it is the open blocker for the every-row gate `P01.S03`. The ARM Linux runner and the macOS ARM64 runner were both offline at the time of this record, so no re-run could be attempted.

Retroactive execution record for evidence produced on 2026-07-22.

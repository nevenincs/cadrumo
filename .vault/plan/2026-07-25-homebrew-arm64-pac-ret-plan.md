---
tags:
  - '#plan'
  - '#homebrew-arm64-pac-ret'
date: '2026-07-25'
modified: '2026-07-25'
tier: L1
related:
  - '[[2026-07-22-homebrew-arm64-pac-ret-adr]]'
  - '[[2026-07-17-post-release-distribution-plan]]'
---

# `homebrew-arm64-pac-ret` plan

- [ ] `S01` - Bring the self-hosted Linux ARM64 runner back online, since it was offline at record time and no diagnosis can proceed without it, OPERATOR-GATED as a host action; `operator action, self-hosted Linux ARM64 host`.
- [ ] `S02` - Reproduce the argon2-cffi-bindings 25.1.0 source build dying with exit -4 SIGILL under the Homebrew python 3.13 toolchain, capturing the failing compiler invocation rather than only the installer summary; `self-hosted Linux ARM64 host, brew log`.
- [ ] `S03` - Resolve the toolchain fault so the homebrew-linux-arm64 row builds, without weakening any preflight or pinning around the failure in a way that ships an untested binary to that platform; `self-hosted Linux ARM64 host toolchain`.
- [ ] `S04` - Re-run the Homebrew acquisition gate on all three claimed rows and record a passing homebrew-linux-arm64 evidence row, since two of three already pass and only this row blocks the claim; `.github/workflows/packaging-homebrew.yml`.
- [ ] `S05` - Decide and record whether homebrew-linux-arm64 is claimed or dropped from the support matrix if the toolchain fault proves unresolvable, because an unclaimed row must not silently read as an untested claim; `docs/updates.md, .vault/adr/`.

## Description

## Steps

## Parallelization

## Verification

## Context

Accepted ADR carrying no plan. The homebrew-linux-arm64 distribution row fails on an argon2-cffi-bindings 25.1.0 source build dying with SIGILL under the Homebrew python 3.13 toolchain on the self-hosted Linux ARM64 runner. Host-side fix; that runner was offline at record time.

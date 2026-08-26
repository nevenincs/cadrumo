---
tags:
  - '#plan'
  - '#homebrew-arm64-pac-ret'
date: '2026-07-25'
modified: '2026-07-28'
body_hash: 'sha256:4762346d5c4ecf9f29f6e999a4b440ec15687179e895fb2fac97742573f4a0a4'
tier: L1
related:
  - '[[2026-07-22-homebrew-arm64-pac-ret-adr]]'
  - '[[2026-07-17-post-release-distribution-plan]]'
  - '[[2026-07-28-homebrew-arm64-pac-ret-evidence-row-blocker-chain-audit]]'
---
# `homebrew-arm64-pac-ret` plan

- [x] `S01` - Bring the self-hosted Linux ARM64 runner back online, since it was offline at record time and no diagnosis can proceed without it, OPERATOR-GATED as a host action; `operator action, self-hosted Linux ARM64 host`.
- [x] `S02` - Reproduce the argon2-cffi-bindings 25.1.0 source build dying with exit -4 SIGILL under the Homebrew python 3.13 toolchain, capturing the failing compiler invocation rather than only the installer summary; `self-hosted Linux ARM64 host, brew log`.
- [x] `S03` - Resolve the toolchain fault so the homebrew-linux-arm64 row builds, without weakening any preflight or pinning around the failure in a way that ships an untested binary to that platform; `self-hosted Linux ARM64 host toolchain`.
- [x] `S04` - Re-run the Homebrew acquisition gate on all three claimed rows and record a passing homebrew-linux-arm64 evidence row, since two of three already pass and only this row blocks the claim; `.github/workflows/packaging-homebrew.yml`.
- [x] `S05` - Decide and record whether homebrew-linux-arm64 is claimed or dropped from the support matrix if the toolchain fault proves unresolvable, because an unclaimed row must not silently read as an untested claim; `docs/updates.md, .vault/adr/`.
## Description

Carry the accepted Linux arm64 pointer-authentication decision from a landed formula fix to a passing `homebrew-linux-arm64` distribution-evidence row.

The decision is already implemented: the formula generator drops the branch-protection flag under a Linux-and-arm guard and installs the two cffi-dependent resources with build isolation disabled. What the decision does not yet have is its evidence row. Two of the three Homebrew rows hold passing records; this feature exists to earn the third, which is the one the accepted record keeps required at full scope.

## Steps

The first three steps clear the diagnosis and the fix, and are closed: the Linux ARM64 runner is online, the fault is characterised at the instruction level, and the guarded mitigation is landed and proven on the real reproducer.

The fifth step settles the support-matrix question and is closed: its condition never triggered, so the row is claimed rather than dropped, and a gate rather than prose keeps that claim from reading as proof.

The fourth step -- minting the row through the acquisition gate -- is the remainder, and it is gated outside this feature. Its blocker chain is recorded in the feature's audit.

## Parallelization

Effectively serial. The diagnosis precedes the fix, the fix precedes the evidence row, and the support-matrix decision depends on whether the fix succeeded.

The one genuine independence is the support-matrix decision against the evidence run: the row can be decided claimed once the fault is resolved, without waiting for its proof to be minted, because claiming and proving are deliberately separate facts.

## Verification

The mitigation is verified by three consecutive green source installs on the Apple-virtualization arm64 container, with the compiled extensions imported under eager binding and an argon2 hash computed through the installed package -- the real reproducer, not a simulation. The generator's own suite pins the guarded form and passes at HEAD, run with parallel workers disabled because every test in it is serial-marked.

The support-matrix claim is verified by the distribution-claims gate, which permits a user-facing acquisition instruction only when a self-consistent, passing evidence record exists for every row backing it, and which carries a positive control so it cannot pass merely by scanning a silent corpus.

The feature is not verified until the acquisition gate emits a passing `homebrew-linux-arm64` record. Until then the row is committed to and unproven, which is the state the claims gate is designed to hold safely.

## Context

Accepted ADR carrying no plan. The homebrew-linux-arm64 distribution row fails on an argon2-cffi-bindings 25.1.0 source build dying with SIGILL under the Homebrew python 3.13 toolchain on the self-hosted Linux ARM64 runner. Host-side fix; that runner was offline at record time.

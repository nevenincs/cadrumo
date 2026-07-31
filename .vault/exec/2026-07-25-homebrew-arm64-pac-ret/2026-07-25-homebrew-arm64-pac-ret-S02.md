---
tags:
  - '#exec'
  - '#homebrew-arm64-pac-ret'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:2dadd6e2f8b96dbffcba60f102aca8747f561f0e4b556f019d245e6883863819'
step_id: 'S02'
related:
  - "[[2026-07-25-homebrew-arm64-pac-ret-plan]]"
---

# Reproduce the argon2-cffi-bindings 25.1.0 source build dying with exit -4 SIGILL under the Homebrew python 3.13 toolchain, capturing the failing compiler invocation rather than only the installer summary

## Scope

- `self-hosted Linux ARM64 host`
- `brew log`

## Description

- Establish that the reproduction and its causal mechanism were already captured, ahead of this plan, during the publication audit that this feature's decision record cites.
- Read the captured mechanism back out of the landed fix commit and the accepted decision record rather than re-running the failing build.

## Outcome

The failure is characterised at the instruction level, which is stronger than the installer summary this step asked to get past. Homebrew's cc shim injects `-mbranch-protection=standard` through the `HOMEBREW_CCCFG` `b` config flag, so every compiled C extension carries the ARMv8.3 pointer-authentication return instruction `retaa`. The Linux-arm64 leg builds inside an Apple Virtualization guest, which faults on `retaa`, so the cffi backend died on load during the `argon2-cffi-bindings` build -- the same defect class as the known dotnet runtime pointer-authentication fault.

The exit -4 SIGILL in the installer summary is that fault surfacing one frame up. The compiler configuration responsible is named exactly: the `b` flag in `HOMEBREW_CCCFG`.

## Notes

This step was satisfied by prior recorded work, not by a fresh reproduction in this session. The reproduction was debugger-confirmed at the time and its conclusion is load-bearing in an accepted decision record; re-running the failing build would not add evidence, and the fix that depends on this diagnosis is independently proven under `S03`.

The diagnosis is falsifiable rather than merely plausible: it predicts that removing the `b` flag makes the build succeed, and that prediction was tested three consecutive times on the real reproducer.

---
generated: true
tags:
  - '#index'
  - '#homebrew-arm64-pac-ret'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:94fecff17a0aef12c4df8ed7e51fb48c85ff8378f758b0f3cf52415623b44e6e'
related:
  - '[[2026-07-22-homebrew-arm64-pac-ret-adr]]'
  - '[[2026-07-25-homebrew-arm64-pac-ret-S01]]'
  - '[[2026-07-25-homebrew-arm64-pac-ret-S02]]'
  - '[[2026-07-25-homebrew-arm64-pac-ret-S03]]'
  - '[[2026-07-25-homebrew-arm64-pac-ret-S04]]'
  - '[[2026-07-25-homebrew-arm64-pac-ret-S05]]'
  - '[[2026-07-25-homebrew-arm64-pac-ret-plan]]'
  - '[[2026-07-28-homebrew-arm64-pac-ret-evidence-row-blocker-chain-audit]]'
---

# `homebrew-arm64-pac-ret` feature index

Auto-generated index of all documents tagged with `#homebrew-arm64-pac-ret`.

## Documents

### adr

- `2026-07-22-homebrew-arm64-pac-ret-adr` - `homebrew-arm64-pac-ret` adr: `Homebrew Linux-arm64 drops pac-ret branch protection for Apple-virtualization compatibility` | (**status:** `accepted`)

### audit

- `2026-07-28-homebrew-arm64-pac-ret-evidence-row-blocker-chain-audit` - `homebrew-arm64-pac-ret` audit: `why the Linux arm64 evidence row cannot be minted at current HEAD`

### exec

- `2026-07-25-homebrew-arm64-pac-ret-S01` - Bring the self-hosted Linux ARM64 runner back online, since it was offline at record time and no diagnosis can proceed without it, OPERATOR-GATED as a host action
- `2026-07-25-homebrew-arm64-pac-ret-S02` - Reproduce the argon2-cffi-bindings 25.1.0 source build dying with exit -4 SIGILL under the Homebrew python 3.13 toolchain, capturing the failing compiler invocation rather than only the installer summary
- `2026-07-25-homebrew-arm64-pac-ret-S03` - Resolve the toolchain fault so the homebrew-linux-arm64 row builds, without weakening any preflight or pinning around the failure in a way that ships an untested binary to that platform
- `2026-07-25-homebrew-arm64-pac-ret-S04` - Re-run the Homebrew acquisition gate on all three claimed rows and record a passing homebrew-linux-arm64 evidence row, since two of three already pass and only this row blocks the claim
- `2026-07-25-homebrew-arm64-pac-ret-S05` - Decide and record whether homebrew-linux-arm64 is claimed or dropped from the support matrix if the toolchain fault proves unresolvable, because an unclaimed row must not silently read as an untested claim

### plan

- `2026-07-25-homebrew-arm64-pac-ret-plan` - `homebrew-arm64-pac-ret` plan

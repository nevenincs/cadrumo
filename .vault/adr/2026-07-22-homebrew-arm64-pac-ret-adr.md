---
tags:
  - '#adr'
  - '#homebrew-arm64-pac-ret'
date: '2026-07-22'
modified: '2026-07-22'
body_hash: 'sha256:0c81ec84257fe69df67575f4287fe13a1c6ea2001cbaf020a16758bb9592b203'
related:
  - "[[2026-07-21-post-release-distribution-v0-2-1-publication-audit]]"
---

# `homebrew-arm64-pac-ret` adr: `Homebrew Linux-arm64 drops pac-ret branch protection for Apple-virtualization compatibility` | (**status:** `accepted`)

## Problem Statement

The Homebrew formula for cadrumo builds every compiled C extension from source
on the installing machine. Homebrew's cc shim injects
`-mbranch-protection=standard` (pac-ret) via the `HOMEBREW_CCCFG` `b` config
flag, so every extension carries the ARMv8.3 pointer-authentication return
instruction `retaa`. Apple Virtualization.framework guests fault (SIGILL) on
`retaa` — the same defect class as dotnet/runtime issue 122608 — and
colima/Docker Desktop VMs on Apple silicon are both the project's Linux-arm64
build/evidence host and the dominant real-world Linux-arm64 environment. With
pac-ret on, the formula is uninstallable there: the cffi backend crashes on
load during the `argon2-cffi-bindings` build (root cause and elimination trail
in the related publication audit; fix commit `73120f57e8`).

A ruling is needed on the security-vs-compatibility tradeoff: disabling
pac-ret removes a return-address-integrity hardening from the compiled
extensions of the Homebrew distribution.

## Considerations

- pac-ret only functions on hardware/hypervisors that execute PAC; the
  faulting Apple-virtualization guests gain zero protection from it — they
  cannot run the instruction at all.
- The primary distribution channel (PyPI wheels) ships extensions built
  without Homebrew's pac-ret injection; a pac-free Homebrew source build is at
  parity with the primary channel, not below it.
- Native macOS arm64 executes pointer authentication correctly; dropping the
  hardening there would be a real, unnecessary loss.
- Linux-arm64 hardware with PAC (e.g. recent Graviton) would run `retaa` fine,
  but the installing formula cannot reliably detect "Apple virtualization
  guest" at install time, and Homebrew-on-Linux arm64 is a best-effort tier.
- The `homebrew-linux-arm64` distribution-evidence row is minted on exactly
  this Apple-virtualization host class; an uninstallable formula blocks the
  release matrix permanently.

## Considered options

- **Keep pac-ret everywhere (reject the fix):** preserves hardening on paper;
  formula is uninstallable in the dominant and evidence-bearing Linux-arm64
  environment. Rejected — a hardening that makes the artifact unusable on its
  supported target is net-negative.
- **Drop pac-ret unconditionally (fix as first committed in `73120f57e8`):**
  simplest, deterministic; but also strips the hardening from native macOS
  arm64 installs where PAC works and has value. Rejected in favour of scoping.
- **Drop pac-ret on Linux arm64 only (chosen):** guard the `HOMEBREW_CCCFG`
  `b` deletion with `OS.linux? && Hardware::CPU.arm?`. macOS arm64 and
  x86-64 keep whatever branch-protection Homebrew configures; Linux arm64
  builds pac-free and installs everywhere including Apple-virtualization
  guests.
- **Detect the hypervisor at install time and drop pac-ret only there:**
  no reliable, supported detection surface from a formula; fragile. Rejected.

## Constraints

- Homebrew forbids overriding compiler flags per-resource; `HOMEBREW_CCCFG`
  is the only sanctioned lever over the shim, and it applies to the whole
  `install` block.
- The `b`-drop covers direct venv resource builds only. Any resource whose
  PEP 517 build-isolation overlay must compile-and-load cffi still faults and
  MUST install with `build_isolation: false` so it builds against the
  pac-free venv cffi, with its build backend pinned as a venv resource. In
  the current 70-resource set that is exactly `argon2-cffi-bindings` (backend:
  `setuptools-scm` 8.x) and `cryptography` (backend: `maturin`). A future
  resource that imports cffi at build time joins this set.
- The mitigation must live in the generated formula (`packaging/homebrew/generate.py`);
  the generator is the single authoring surface for the tap.

## Implementation

The formula generator emits, inside `def install`, a guarded deletion of the
`b` flag from `HOMEBREW_CCCFG` under `OS.linux? && Hardware::CPU.arm?`, keeps
the isolation-off installs and their pinned build-backend resources
unconditionally (harmless and deterministic on all platforms), and the
generator unit suite pins the guarded form. Initial unconditional fix:
commit `73120f57e8` (argon2 leg); the Linux-arm64 scoping refinement and the
cryptography leg (isolation-off with a pinned `maturin` resource, excluded
from the batch install and installed after the batch so maturin is present)
land with this ADR. The real-formula arm64 proof gate is three consecutive
green `brew install` runs on the Apple-virtualization container including an
argon2 hash and cffi import under `LD_BIND_NOW=1`.

## Rationale

Compatibility wins because the protection being sacrificed is inoperative
precisely where it breaks installation: Apple-virtualization guests cannot
execute PAC, so pac-ret buys nothing there while making the package
uninstallable. Scoping the deletion to Linux arm64 confines the loss to the
tier where the dominant environment faults and where the primary PyPI channel
already ships pac-free builds; native macOS arm64 — where PAC is real —
retains the hardening. The `homebrew-linux-arm64` evidence row remains
required and is provable on the standing Apple-virtualization runner with
this formula.

## Consequences

- Homebrew Linux-arm64 installs lose return-address-integrity hardening in
  their compiled C extensions, including on PAC-capable Linux-arm64 hardware;
  this is an accepted, documented support-level statement for that tier.
- macOS arm64 Homebrew installs keep pac-ret; no change to x86-64.
- The `homebrew-linux-arm64` distribution-evidence row stays required at full
  scope; no support-level carve-out is needed.
- Revisit trigger: when Apple Virtualization.framework executes PAC in guests
  (or the Linux-arm64 lane moves to non-Apple hosting), the guard can be
  removed and pac-ret restored; the guarded form makes that a one-line
  generator change.

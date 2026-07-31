---
tags:
  - '#exec'
  - '#homebrew-arm64-pac-ret'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:b4e1d05c123ce25a692346016b5f251023c7460ef20a501c4f46dcb4203f5ebe'
step_id: 'S03'
related:
  - "[[2026-07-25-homebrew-arm64-pac-ret-plan]]"
---

# Resolve the toolchain fault so the homebrew-linux-arm64 row builds, without weakening any preflight or pinning around the failure in a way that ships an untested binary to that platform

## Scope

- `self-hosted Linux ARM64 host toolchain`

## Description

- Delete the `b` flag from `HOMEBREW_CCCFG` inside the formula's install block, guarded to Linux arm64 so no other platform loses branch protection.
- Install the two resources whose build-isolation overlay must compile and load cffi with isolation disabled, so they build against the pac-free virtual environment cffi rather than a fresh overlay copy that re-inherits the shim's setting.
- Pin those resources' build backends as virtual-environment resources, and prepend the virtual environment's bin directory to PATH so the Rust build backend resolves by bare name.
- Re-run the generator's own unit suite at current HEAD to confirm the guarded form is still pinned.

## Outcome

The toolchain fault is resolved in the formula generator, which is the single authoring surface for the tap. The guarded deletion is scoped by an explicit Linux-and-arm test, so macOS arm64 keeps pointer-authentication hardening where the hardware actually executes it, and x86-64 is untouched.

Proven on the real reproducer, not in simulation: three consecutive green source installs on the Apple-virtualization arm64 container, with the compiled extensions imported under eager binding and an argon2 hash computed through the installed package.

The generator unit suite passes at HEAD -- 6 passed, run with workers disabled because every test in it is serial-marked. The suite pins the guarded form, so a regression that silently restored the unconditional deletion, or dropped the guard, would fail it.

## Notes

No preflight was weakened and nothing was pinned around the failure to hide it, which was this step's explicit constraint. The fix removes a compiler flag whose protection is inoperative in the environment that faults on it -- an Apple-virtualization guest cannot execute the instruction at all -- so the mitigation costs nothing where it applies and is scoped away from where the hardening is real. The accepted decision record carries that tradeoff and its revisit trigger.

A first pass at running the generator suite reported a clean result while executing nothing: the default marker selection deselected every test, and the runner additionally held the serial-marked tests out because parallel workers were active. The green was re-run with workers disabled before it was believed.

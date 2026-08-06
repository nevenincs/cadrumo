---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-16'
modified: '2026-07-17'
body_hash: 'sha256:ab7a46128039af915e5898479326e544d79395e7534adb534af48042be8cd5be'
step_id: 'S21'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Generate a pinned Python virtualenv formula and immutable tap snapshot from the cohort

## Scope

- `packaging/homebrew/generate.py`

## Description

- Read the exact root and companion source-distribution identities from the supplied cohort.
- Resolve the default and agent dependency closure from `uv.lock` for every declared macOS and Linux architecture.
- Generate one deterministic `Language::Python::Virtualenv` formula with immutable release and PyPI resource hashes.
- Preserve architecture-specific markers with nested Homebrew platform blocks.

## Outcome

- The generator emits one pinned tap snapshot with the root source archive, both mandatory companions, locked resources, Python 3.13, both executables, and a command-level test block.
- Mutable release URLs, foreign companion metadata, missing lock material, and unsupported platform subsets fail closed.

## Notes

- Homebrew installation and platform execution remain open under S23 and S24.
